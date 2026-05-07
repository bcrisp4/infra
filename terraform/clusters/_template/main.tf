# Cluster: {{cluster_name}}
#
# Copy this template to create a new cluster:
#   cp -r _template ../{{cluster_name}}
#   cd ../{{cluster_name}}
#   # Update backend.tf with workspace name
#   # Update terraform.tfvars with cluster configuration
#   # Uncomment and configure the module below

terraform {
  required_version = ">= 1.14"

  # Add provider requirements for your cluster module here
  # required_providers {
  #   hcloud = {
  #     source  = "hetznercloud/hcloud"
  #     version = "~> 1.45"
  #   }
  # }
}

# Uncomment and configure for your provider
# module "cluster" {
#   source = "../../modules/k8s-cluster/<provider>"
#
#   cluster_name = var.cluster_name
#
#   # Add provider-specific configuration here
# }
