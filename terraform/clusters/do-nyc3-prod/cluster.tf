# DigitalOcean Kubernetes (DOKS) cluster
#
# Single control plane (non-HA) with autoscaling worker nodes.
# VPC-native networking with dedicated pod and service subnets.

resource "digitalocean_kubernetes_cluster" "main" {
  name     = var.cluster_name
  region   = "nyc3"
  version  = "1.34"
  vpc_uuid = digitalocean_vpc.main.id
  ha       = false

  # VPC-native networking with Cilium eBPF
  # These subnets must not overlap with the VPC CIDR or each other
  # Note: 10.244.0.0/16 is reserved by DigitalOcean internally
  cluster_subnet = "10.200.0.0/16"
  service_subnet = "10.201.0.0/16"

  # Default node pool
  node_pool {
    name       = "default"
    size       = "s-2vcpu-4gb"
    node_count = 2
    auto_scale = true
    min_nodes  = 2
    max_nodes  = 4

    labels = {
      pool = "default"
    }
  }

  # Automatic maintenance and upgrades
  maintenance_policy {
    day        = "sunday"
    start_time = "04:00"
  }

  auto_upgrade  = true
  surge_upgrade = true

  # Clean up associated resources when cluster is destroyed
  destroy_all_associated_resources = true
}
