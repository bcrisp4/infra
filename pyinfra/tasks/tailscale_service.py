"""Expose local services on the tailnet as Tailscale Services.

For each configured service, renders a Tailscale Services configuration file
(huJSON) and applies it declaratively with `tailscale serve set-config`, which
advertises the node as a host for that service. tailscaled terminates TLS on the
service VIP/MagicDNS name (cert auto-provisioned) and reverse-proxies to a local
backend.

Currently exposes Prometheus (svc:prometheus -> http://127.0.0.1:<port>) and
Grafana (svc:grafana -> http://127.0.0.1:<port>). Each service object, ACL grant,
and auto-approval is defined in Terraform (terraform/global/tailscale.tf); the Pi
only advertises here.

`tailscale serve --service` config persists across reboots (stored in tailscaled
state), and `set-config` re-applies declaratively only when the rendered config
changes. Requires tailscale >= 1.86.0 and a tag-based node identity (the Pi is
tag:home); both hold on rpi5-4cpu-16gb-home (tailscale 1.98.4).

Gated on `tailscale_serve_enabled` host/group data so other hosts no-op.
"""

import json
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import files, server

CONFIG_DIR = "/etc/tailscale"

# Tailscale Services config file schema version (see
# tailscale.com/kb/1589/tailscale-services-configuration-file).
CONFIG_VERSION = "0.0.1"

# tailscaled and the local service ports share the host loopback; the backend is
# plain HTTP, TLS is terminated by tailscaled at the service edge.
BACKEND_HOST = "127.0.0.1"


def _config_path(service_name: str) -> str:
    """Per-service serve config path, e.g. svc:grafana -> serve-grafana.json."""
    short = service_name.split(":", 1)[-1]
    return f"{CONFIG_DIR}/serve-{short}.json"


def _render_serve_config(https_port: int, backend_port: int) -> str:
    """Render the per-service Tailscale serve config (huJSON).

    This is the single-service (flattened) form consumed by
    `tailscale serve set-config --service=<svc>`: a `version` plus an
    `endpoints` map, with the service named by the CLI flag (not in the file).
    It matches `tailscale serve get-config --service=<svc>` output verbatim.

    The endpoint key is `tcp:<port>` even for HTTPS: tailscaled terminates TLS
    at the service edge and the `http://` backend scheme signals a plain-HTTP
    upstream (`--https=443 http://...` canonicalizes to `tcp:443 -> http://...`).
    """
    backend = f"http://{BACKEND_HOST}:{backend_port}"
    config = {
        "version": CONFIG_VERSION,
        "endpoints": {
            f"tcp:{https_port}": backend,
        },
    }
    return json.dumps(config, indent=2) + "\n"


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
        path = _config_path(name)

        config = files.put(
            name=f"Render {path}",
            src=StringIO(_render_serve_config(svc["https_port"], svc["backend_port"])),
            dest=path,
            user="root",
            group="root",
            mode="0644",
            _sudo=True,
        )

        # Declaratively apply (and advertise) the service config only when it
        # changes. `advertised` defaults true, so set-config advertises the node
        # as a service host; no separate `tailscale serve advertise` step is
        # needed. Flags must precede the positional <file>: the Go flag parser
        # stops at the first non-flag arg, so `set-config <file> --service=...`
        # drops --service and errors "must specify filename".
        server.shell(
            name=f"Apply Tailscale serve config for {name}",
            commands=[f"tailscale serve set-config --service={name} {path}"],
            _if=config.did_change,
            _sudo=True,
        )
