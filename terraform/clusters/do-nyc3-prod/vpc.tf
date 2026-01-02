# VPC for the do-nyc3-prod cluster
#
# All cluster resources (nodes, load balancers) are placed in this VPC
# for private networking between components.

resource "digitalocean_vpc" "main" {
  name        = var.cluster_name
  region      = "nyc3"
  description = "VPC for ${var.cluster_name} Kubernetes cluster"
  ip_range    = "10.100.0.0/16"
}
