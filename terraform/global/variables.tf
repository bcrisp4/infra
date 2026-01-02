variable "clusters" {
  description = "Map of cluster names to their configuration"
  type = map(object({
    tags = optional(list(string), [])
  }))
  default = {}
}

variable "onepassword_vault" {
  description = "1Password vault ID for storing secrets"
  type        = string
}
