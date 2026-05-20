"""Base system config reusable across all homelab hosts.

Reads `timezone` and `base_packages` from host/group data. Override per host
in inventory.py or per group in group_data/<group>.py.

Package upgrades are handled async by unattended-upgrades, not here.
"""

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.facts.server import Command
from pyinfra.operations import apt, server


@deploy("Base system config")
def base() -> None:
    timezone = host.data.get("timezone", "UTC")
    packages = host.data.get("base_packages", [])

    if packages:
        apt.packages(
            name="Install base packages",
            packages=packages,
            _sudo=True,
        )

    current_tz = host.get_fact(
        Command,
        command="timedatectl show --property=Timezone --value",
    )
    if current_tz.strip() != timezone:
        server.shell(
            name=f"Set timezone to {timezone}",
            commands=[f"timedatectl set-timezone {timezone}"],
            _sudo=True,
        )
