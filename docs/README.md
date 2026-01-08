# Documentation

This documentation is organized using the [Divio documentation system](https://documentation.divio.com/).

## Quick Links

| I want to... | Go to |
|--------------|-------|
| Learn how this repo works | [Tutorials](#tutorials) |
| Complete a specific task | [How-to Guides](#how-to-guides) |
| Look up technical details | [Reference](#reference) |
| Understand why things work this way | [Explanation](#explanation) |
| Debug a problem | [Troubleshooting](#troubleshooting) |
| See pending work | [Tasks](#tasks) |

## Tutorials

Step-by-step guides for learning the system.

- [Add a New Cluster](tutorials/add-new-cluster.md) - Provision infrastructure and bootstrap ArgoCD
- [Deploy Your First App](tutorials/deploy-first-app.md) - Create and deploy an application with GitOps

## How-to Guides

Task-oriented recipes for specific goals.

- [Deploy a New App](how-to/deploy-new-app.md) - Create umbrella charts and cluster configs
- [Add Namespace to Mesh](how-to/add-namespace-to-mesh.md) - Enable Linkerd mTLS for an app
- [Update Linkerd Edge](how-to/update-linkerd-edge.md) - Upgrade to a new Linkerd edge release
- [Configure ArgoCD Webhook with Tailscale Funnel](how-to/argocd-webhook-tailscale-funnel.md) - Enable instant GitOps sync
- [Configure Strimzi Kafka with Linkerd](how-to/strimzi-kafka-linkerd.md) - Run Kafka in the service mesh
- [Query Logs](how-to/query-logs.md) - LogQL examples for querying pod logs
- [Query Kubernetes Events](how-to/query-kubernetes-events.md) - LogQL examples for querying K8s events

## Reference

Technical descriptions and specifications.

### Architecture

- [Architecture Overview](reference/architecture.md) - High-level system design

### Components

- [External Secrets Operator](reference/external-secrets.md) - ESO configuration with 1Password
- [1Password Terraform Provider](reference/onepassword-terraform.md) - Terraform provider notes
- [Tailscale Operator](reference/tailscale-operator.md) - Kubernetes operator configuration
- [Linkerd](reference/linkerd.md) - Service mesh architecture and configuration
- [ArgoCD Manifests](reference/argocd-manifests.md) - ApplicationSet and Go template patterns
- [CloudNativePG Backup](reference/cloudnative-pg-backup.md) - Barman plugin for PostgreSQL backups
- [Grafana Datasources](reference/grafana-datasources.md) - Datasource provisioning pitfalls
- [Miniflux](reference/miniflux.md) - RSS reader deployment and configuration
- [Mimir Tenancy](reference/mimir-tenancy.md) - Multi-tenant metrics configuration
- [n8n](reference/n8n.md) - Workflow automation deployment and configuration
- [Dependabot](reference/dependabot.md) - Automated dependency updates
- [Paperless-ngx](reference/paperless-ngx.md) - Document management deployment and configuration
- [Metrics Architecture](reference/metrics-architecture.md) - Observability stack design
- [Logging Architecture](reference/logging-architecture.md) - Log collection and storage design
- [Tracing Architecture](reference/tracing-architecture.md) - Distributed tracing storage design

## Explanation

Background and conceptual information.

- [Why Linkerd Edge Releases](explanation/linkerd-edge-releases.md) - Rationale for using edge releases

## Troubleshooting

Debugging guides for common issues.

- [Metrics Issues](troubleshooting/metrics.md) - Prometheus, Mimir, and scraping problems
- [Linkerd Issues](troubleshooting/linkerd.md) - Service mesh connectivity problems
- [ArgoCD Issues](troubleshooting/argocd.md) - Sync failures and webhook problems

## Tasks

Pending work and future improvements.

- [Tailscale Operator 1.94 Linkerd](tasks/tailscale-operator-1.94-linkerd.md) - Upgrade for Linkerd compatibility

## In-tree Documentation

Component-specific READMEs that live alongside their code:

### Terraform
- [Bootstrap](../terraform/bootstrap/README.md) - TFC workspace provisioning
- [Global](../terraform/global/README.md) - Cross-cluster resources
- [Cluster Modules](../terraform/modules/k8s-cluster/README.md) - Provider-specific modules
- [Cluster Template](../terraform/clusters/_template/README.md) - New cluster template

### Kubernetes
- [Base](../kubernetes/base/README.md) - Shared configurations
- [Cluster Template](../kubernetes/clusters/_template/README.md) - New cluster template
- [App Template](../kubernetes/apps/_template/README.md) - New app template
