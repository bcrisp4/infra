variable "cluster_name" {
  description = "Name of the cluster (must match global Terraform cluster config)"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version to deploy"
  type        = string
  default     = null
}

# Add provider-specific variables below
