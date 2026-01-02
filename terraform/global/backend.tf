terraform {
  cloud {
    organization = "bc4"

    workspaces {
      name = "global"
    }
  }
}
