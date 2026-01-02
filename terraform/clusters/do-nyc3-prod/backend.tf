terraform {
  cloud {
    organization = "bc4"

    workspaces {
      name = "do-nyc3-prod"
    }
  }
}
