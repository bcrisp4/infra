"""Top-level pyinfra deploy: applies all base config to every host in inventory."""

from tasks.base import base
from tasks.bns import bns
from tasks.dhcp import dnsmasq
from tasks.grafana import grafana
from tasks.image_renderer import image_renderer
from tasks.network import static_network
from tasks.nodeexporter import node_exporter
from tasks.podman import install_podman
from tasks.podman_network import podman_networks
from tasks.prometheus import prometheus
from tasks.tailscale_service import tailscale_service
from tasks.unattended_upgrades import unattended_upgrades

base()
unattended_upgrades()
static_network()
install_podman()
podman_networks()
bns()
node_exporter()
prometheus()
image_renderer()
grafana()
tailscale_service()
dnsmasq()
