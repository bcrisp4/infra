# Node firewall for the do-nyc3-prod cluster
#
# Blocks ALL inbound public traffic to nodes.
# Allows all outbound traffic for pulling images, DNS, etc.
# VPC-internal traffic is NOT affected by cloud firewalls.

resource "digitalocean_firewall" "k8s_nodes" {
  name = "${var.cluster_name}-nodes"

  # Apply to DOKS nodes via the auto-generated cluster tag
  tags = ["k8s:${digitalocean_kubernetes_cluster.main.id}"]

  # No inbound rules = block all inbound public traffic
  # This is intentional - nodes should not be accessible from the internet.
  # VPC-internal traffic (pod-to-pod, control plane) still works.

  # Allow all outbound TCP (for pulling images, API calls, etc.)
  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  # Allow all outbound UDP (for DNS, NTP, etc.)
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  # Allow outbound ICMP (for network diagnostics)
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
