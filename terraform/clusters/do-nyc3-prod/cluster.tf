# DigitalOcean Kubernetes (DOKS) cluster
#
# Single control plane (non-HA) with autoscaling worker nodes.
# VPC-native networking with dedicated pod and service subnets.

resource "digitalocean_kubernetes_cluster" "main" {
  name     = var.cluster_name
  region   = "nyc3"
  version  = "1.34.1-do.2"
  vpc_uuid = digitalocean_vpc.main.id
  ha       = false

  # VPC-native networking with Cilium eBPF
  # These subnets must not overlap with the VPC CIDR or each other
  # Note: 10.244.0.0/16 is reserved by DigitalOcean internally
  cluster_subnet = "10.200.0.0/16"
  service_subnet = "10.201.0.0/16"

  # Default node pool - DOES NOT EXIST, deleted via DigitalOcean UI
  #
  # The terraform provider requires this block for schema validation, but the
  # actual pool was deleted after creating the workers pool. DOKS allows this
  # when at least one other node pool exists. The provider handles the mismatch
  # gracefully - it won't try to recreate the pool.
  #
  # WARNING: Changing 'size' here will trigger cluster replacement!
  node_pool {
    name       = "default"
    size       = "s-2vcpu-4gb"
    node_count = 1
    auto_scale = false
    min_nodes  = 1
    max_nodes  = 1

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

# Primary worker node pool - larger, more cost-efficient instances
resource "digitalocean_kubernetes_node_pool" "workers_8vcpu_16gb" {
  cluster_id = digitalocean_kubernetes_cluster.main.id

  name       = "workers-8vcpu-16gb"
  size       = "s-8vcpu-16gb"
  auto_scale = true
  min_nodes  = 3
  max_nodes  = 5

  labels = {
    pool = "workers-8vcpu-16gb"
  }
}
