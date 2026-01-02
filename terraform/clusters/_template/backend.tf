terraform {
  cloud {
    organization = "bc4"

    workspaces {
      name = "{{cluster_name}}"  # Replace with actual cluster name
    }
  }
}
