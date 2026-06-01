"""Expose local services on the tailnet as Tailscale Services.

For each configured service, applies a `tailscale serve` HTTPS reverse proxy:
tailscaled terminates TLS on :<https_port> (cert auto-provisioned for the
service MagicDNS name) and proxies to a local plain-HTTP backend on the
loopback. Currently exposes Prometheus (svc:prometheus) and Grafana
(svc:grafana). Each service object, ACL grant, and auto-approval is defined in
Terraform (terraform/global/tailscale.tf); the Pi only advertises here.

Why the `--https` CLI form and NOT `serve set-config <file>`:
The flattened set-config huJSON schema has a single per-endpoint protocol field
(see tailscale ipn/conffile/serveconf.go) that conflates the LISTENER type with
the BACKEND scheme. `serveTypeFromConfString` (cmd/tailscale/cli/serve_v2.go)
maps that field to the listener type, so `{"tcp:443": "http://127.0.0.1:3000"}`
is parsed as a PLAINTEXT http listener -- TLS is never terminated and browsers
fail with a TLS error. There is no flattened value that means "listen HTTPS,
proxy to an HTTP backend": `serve get-config` even emits the backend scheme
(`http://...`) for an HTTPS service, so set-config cannot round-trip it. The
`tailscale serve --service=<svc> --https=<port> http://<backend>` CLI form keeps
the listener (the `--https` flag) and the backend (the positional target)
separate, which is the only way to express this.

Idempotency: re-applying the same HTTPS config is safe -- tailscaled only
rejects a change of serve TYPE on a port (ipn/ipnlocal/serve.go), not a
same-type re-apply. A per-service marker file records the desired state and
drives change detection so the serve command runs only when it changes.

Requires tailscale >= 1.86.0 and a tag-based node identity (the Pi is tag:home);
both hold on rpi5-4cpu-16gb-home (tailscale 1.98.4).

Gated on `tailscale_serve_enabled` host/group data so other hosts no-op.
"""

from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server

CONFIG_DIR = "/etc/tailscale"

# tailscaled and the local service ports share the host loopback; the backend is
# plain HTTP, TLS is terminated by tailscaled at the service edge.
BACKEND_HOST = "127.0.0.1"


def _short_name(service_name: str) -> str:
    """`svc:grafana` -> `grafana`."""
    return service_name.split(":", 1)[-1]


def _state_path(service_name: str) -> str:
    """Per-service desired-state marker, e.g. /etc/tailscale/serve-grafana.state.

    This drives change detection only; it is NOT a tailscale config file (the
    config is applied via the `tailscale serve --https` CLI, see module docstring).
    """
    return f"{CONFIG_DIR}/serve-{_short_name(service_name)}.state"


def _legacy_config_path(service_name: str) -> str:
    """Path of the obsolete huJSON set-config file, removed if present.

    Earlier revisions applied serve via `set-config <this file>`, which silently
    configured a plaintext http listener (see module docstring). The file is now
    unused and removed to avoid confusion.
    """
    return f"{CONFIG_DIR}/serve-{_short_name(service_name)}.json"


def _backend_url(backend_port: int) -> str:
    """Loopback HTTP backend the service proxies to."""
    return f"http://{BACKEND_HOST}:{backend_port}"


def _render_state(service_name: str, https_port: int, backend_port: int) -> str:
    """Render the desired-state marker for a service (change-detection only)."""
    lines = [
        "# Desired Tailscale serve state. Drives change detection in",
        "# tasks/tailscale_service.py; NOT a tailscale config file (applied via",
        "# `tailscale serve --https`, not set-config). Do not edit by hand.",
        f"service={service_name}",
        f"https_port={https_port}",
        f"backend={_backend_url(backend_port)}",
    ]
    return "\n".join(lines) + "\n"


@deploy("Configure Tailscale services")
def tailscale_service() -> None:
    if not host.data.get("tailscale_serve_enabled", False):
        return

    services = host.data.get("tailscale_serve_services", [])

    files.directory(
        name="Ensure /etc/tailscale dir",
        path=CONFIG_DIR,
        present=True,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
    )

    for svc in services:
        name = svc["name"]
        https_port = svc["https_port"]
        backend = _backend_url(svc["backend_port"])

        files.file(
            name=f"Remove obsolete set-config file for {name}",
            path=_legacy_config_path(name),
            present=False,
            _sudo=True,
        )

        state = files.put(
            name=f"Render {_state_path(name)}",
            src=StringIO(_render_state(name, https_port, svc["backend_port"])),
            dest=_state_path(name),
            user="root",
            group="root",
            mode="0644",
            _sudo=True,
        )

        # Apply the HTTPS reverse proxy only when the desired state changes.
        # Idempotent: a same-type re-apply is accepted by tailscaled. The
        # listener (--https) and backend (positional, http://) must stay
        # separate -- see the module docstring for why set-config cannot do this.
        server.shell(
            name=f"Apply Tailscale HTTPS serve for {name}",
            commands=[f"tailscale serve --service={name} --https={https_port} {backend}"],
            _if=state.did_change,
            _sudo=True,
        )
