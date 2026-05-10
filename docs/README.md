# Documentation

This documentation is organized using the [Divio documentation system](https://documentation.divio.com/).

## Reference

Technical descriptions and specifications.

### Architecture

- [Architecture Overview](reference/architecture.md) - High-level system design
- [Metrics Architecture](reference/metrics-architecture.md) - Observability stack design
- [Logging Architecture](reference/logging-architecture.md) - Log collection and storage design

### Components

- [External Secrets Operator](reference/external-secrets.md) - ESO configuration with 1Password
- [1Password Terraform Provider](reference/onepassword-terraform.md) - Terraform provider notes
- [Tailscale Operator](reference/tailscale-operator.md) - Kubernetes operator configuration
- [Dependabot](reference/dependabot.md) - Automated dependency updates

## How-to Guides

- [Migrate Ingress to ProxyGroup](how-to/tailscale-proxygroup-ingress.md)
- [Update Terraform Providers](how-to/update-terraform-providers.md)

## In-tree Documentation

- [Bootstrap](../terraform/bootstrap/README.md) - TFC workspace provisioning
- [Global](../terraform/global/README.md) - Cross-cluster resources
- [Cluster Modules](../terraform/modules/k8s-cluster/README.md) - Provider-specific modules
