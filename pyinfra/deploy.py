"""Top-level pyinfra deploy: applies all base config to every host in inventory."""

from tasks.base import base
from tasks.unattended_upgrades import unattended_upgrades

base()
unattended_upgrades()
