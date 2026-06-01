"""Deploy the Grafana image renderer as a rootful podman quadlet.

Renders /etc/containers/systemd/grafana-image-renderer.container from host data,
then ensures grafana-image-renderer.service is running. The quadlet generator
converts the .container file into a runtime systemd unit at daemon-reload.

The image renderer is the standalone remote rendering service (Node + headless
Chromium) that Grafana calls to turn panels/dashboards into PNGs (share image,
alert/report thumbnails, the Grafana MCP get_panel_image tool). Grafana ships no
renderer by default.

Networking: the renderer joins the dedicated `rendering` podman network ONLY (see
tasks/podman_network.py) and publishes NO host port. It is therefore reachable
solely by Grafana, which also joins `rendering` and resolves it by ContainerName
via aardvark-dns (http://grafana-image-renderer:8081). No host, LAN or Tailscale
exposure. Prometheus stays on the separate `monitoring` network and cannot reach
it.

Auth: Grafana 13 refuses to start when a renderer is configured unless
[rendering] renderer_token is changed from its default, so network isolation
alone is not sufficient. We generate a random token on the host once (never in
git, per the repo no-secrets rule) into TOKEN_FILE and inject it into both
containers via `EnvironmentFile=`: the renderer reads it as AUTH_TOKEN, Grafana
as GF_RENDERING_RENDERER_TOKEN (same value -> the X-Auth-Token handshake matches).
The file holds both names so a single EnvironmentFile serves both quadlets.

State: the renderer is stateless -- it writes snapshots to an ephemeral /tmp
inside the container. So, like node-exporter, there is no _render_config, volume
or uid chown, and no SIGHUP reload path; a quadlet change just recreates the
container. The token file is the one piece of on-host state.

Gated on `grafana_image_renderer_enabled` host/group data so other hosts no-op.
"""

from collections.abc import Mapping
from io import StringIO

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, systemd

UNIT_PATH = "/etc/containers/systemd/grafana-image-renderer.container"

# The renderer listens on this port inside the container (its default). No host
# port is published; Grafana reaches it by ContainerName on the rendering network.
CONTAINER_PORT = 8081

# Shared auth-token env file, generated on the host (never committed). Holds both
# AUTH_TOKEN (renderer) and GF_RENDERING_RENDERER_TOKEN (Grafana) set to the same
# random value; both quadlets load it via EnvironmentFile=. grafana.py imports
# TOKEN_FILE so the two stay in sync.
TOKEN_DIR = "/etc/grafana-image-renderer"
TOKEN_FILE = f"{TOKEN_DIR}/renderer-token.env"


def _render_quadlet(data: Mapping) -> str:
    """Render the systemd quadlet .container unit for the image renderer."""
    image = f"{data['grafana_image_renderer_image']}:{data['grafana_image_renderer_image_tag']}"
    lines = [
        "# Rendered by pyinfra tasks/image_renderer.py. Do not edit by hand.",
        "[Unit]",
        "Description=Grafana image renderer - remote PNG rendering",
        "Wants=network-online.target",
        "After=network-online.target",
        # Tolerate a startup loop without permanent give-up: 10 starts per 60s.
        "StartLimitIntervalSec=60s",
        "StartLimitBurst=10",
        "",
        "[Container]",
        f"Image={image}",
        "ContainerName=grafana-image-renderer",
        # Dedicated bridge shared only with Grafana; resolved by ContainerName via
        # aardvark-dns. NO PublishPort: the renderer is reachable solely by Grafana
        # over this network, never the host/LAN/Tailscale.
        "Network=rendering.network",
        # Host-generated token file (AUTH_TOKEN) -> renderer requires a matching
        # X-Auth-Token, which Grafana sends. Same file feeds Grafana's token.
        f"EnvironmentFile={TOKEN_FILE}",
        "",
        "[Service]",
        # First start runs `podman run`, which pulls the ~550MB renderer image
        # inline. The systemd default (90s) is too short on a slow link, so the
        # unit fails before the pull finishes. Give the initial pull headroom;
        # later starts (image cached) are fast and unaffected.
        "TimeoutStartSec=600s",
        # Always restart: covers non-zero exits, panics, OOM-kill (SIGKILL from
        # the cgroup memory ceiling), and uncaught signals.
        "Restart=always",
        "RestartSec=5s",
        # Cgroup ceilings at the systemd unit level. Quadlet passes [Service]
        # through unchanged, so these work across podman versions (vs Memory=/
        # CPUS= in [Container] which require podman >= 5.5).
        f"MemoryMax={data['grafana_image_renderer_memory_max']}",
        f"MemoryHigh={data['grafana_image_renderer_memory_high']}",
        f"CPUQuota={data['grafana_image_renderer_cpu_quota']}",
        f"TasksMax={data['grafana_image_renderer_tasks_max']}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
    ]
    return "\n".join(lines) + "\n"


_DATA_KEYS = (
    "grafana_image_renderer_image",
    "grafana_image_renderer_image_tag",
    "grafana_image_renderer_memory_max",
    "grafana_image_renderer_memory_high",
    "grafana_image_renderer_cpu_quota",
    "grafana_image_renderer_tasks_max",
)


@deploy("Deploy Grafana image renderer")
def image_renderer() -> None:
    if not host.data.get("grafana_image_renderer_enabled", False):
        return

    # HostData is not subscriptable; materialize into a plain dict so the pure
    # renderer stays test-friendly with `data["key"]` access.
    data = {k: host.data.get(k) for k in _DATA_KEYS}

    files.directory(
        name=f"Ensure {TOKEN_DIR}",
        path=TOKEN_DIR,
        present=True,
        user="root",
        group="root",
        mode="0750",
        _sudo=True,
    )

    # Generate the shared auth token once and persist it. Random value is created
    # on the host (not in Python) so it never enters git or pyinfra logs, and only
    # when the file is missing so re-runs keep the same token (no churn / no
    # forced restart). Both var names are written so a single EnvironmentFile
    # serves the renderer (AUTH_TOKEN) and Grafana (GF_RENDERING_RENDERER_TOKEN).
    token_present = host.get_fact(
        Command,
        command=f"test -s {TOKEN_FILE} && echo yes || echo no",
        _sudo=True,
    )
    token_created = token_present.strip() != "yes"
    if token_created:
        server.shell(
            name="Generate renderer auth token (first run only)",
            commands=[
                "umask 077; "
                "t=$(openssl rand -hex 32); "
                "printf 'AUTH_TOKEN=%s\\nGF_RENDERING_RENDERER_TOKEN=%s\\n' "
                f'"$t" "$t" > {TOKEN_FILE}; '
                f"chmod 0600 {TOKEN_FILE}"
            ],
            _sudo=True,
        )

    unit = files.put(
        name="Render /etc/containers/systemd/grafana-image-renderer.container",
        src=StringIO(_render_quadlet(data)),
        dest=UNIT_PATH,
        user="root",
        group="root",
        mode="0644",
        _sudo=True,
    )

    # Boot-time start is handled by `[Install] WantedBy=multi-user.target` in the
    # quadlet file. systemctl enable does not apply to generator-produced units,
    # so we only manage running state here. The renderer is stateless, so a
    # quadlet change just recreates the container (no config-reload path). Also
    # restart when the token was just generated so the container picks it up.

    systemd.service(
        name="Restart grafana-image-renderer.service on quadlet/token change",
        service="grafana-image-renderer.service",
        running=True,
        restarted=True,
        daemon_reload=True,
        _if=lambda: unit.did_change() or token_created,
        _sudo=True,
    )

    systemd.service(
        name="Ensure grafana-image-renderer.service running",
        service="grafana-image-renderer.service",
        running=True,
        _sudo=True,
    )
