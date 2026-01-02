variable "clusters" {
  description = "Map of cluster names to their configuration"
  type = map(object({
    tags = optional(list(string), [])
  }))
  default = {}
}
