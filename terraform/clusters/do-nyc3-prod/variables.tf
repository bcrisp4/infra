variable "cluster_name" {
  description = "Name of the cluster (must match global Terraform cluster config)"
  type        = string
  default     = "do-nyc3-prod"
}

variable "onepassword_vault" {
  description = "1Password vault ID for storing secrets"
  type        = string
}
