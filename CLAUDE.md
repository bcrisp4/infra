# CLAUDE.md

Guidance for Claude Code when working with this infrastructure monorepo.

## CRITICAL: NEVER COMMIT SECRETS OR STATE FILES

**NEVER commit:**
- `*.tfstate` / `*.tfstate.backup` / `*.tfvars` / `.terraform/`
- API keys, tokens, passwords, credentials
- `kubeconfig` / `talosconfig` / private keys (`*.pem`, `*.key`)
- `.env` files with real values

**Before EVERY commit:**
```bash
git diff --cached --name-only | grep -E '\.(tfstate|tfvars)$'
git diff --cached -S"SECRET" -S"TOKEN" -S"PASSWORD" -S"API_KEY"
```

## Commands

```bash
# Scaffold new cluster/app
./scripts/new-cluster.sh <cluster-name>
./scripts/new-app.sh <app-name> [cluster-name]
./scripts/bootstrap-argocd.sh <cluster-name>

# Terraform
cd terraform/<dir> && terraform init && terraform plan && terraform apply

# Helm
cd kubernetes/apps/<app> && helm dependency update
helm show values <chart>  # Get full chart values
```

## Architecture

Infrastructure monorepo for multi-cluster Kubernetes with GitOps. See [docs/reference/architecture.md](docs/reference/architecture.md).

**Terraform:** `bootstrap/` (TFC workspaces) | `global/` (cross-cluster) | `clusters/{cluster}/` (per-cluster)

**Kubernetes:** `apps/{app}/` (umbrella charts) | `clusters/{cluster}/apps/{app}/` (config.yaml + values.yaml)

**Patterns:**
- Cluster naming: `{provider}-{region}-{env}` (e.g., `do-nyc3-prod`)
- Apps auto-deploy when `config.yaml` + `values.yaml` added to cluster

## Current State

- Active cluster: `do-nyc3-prod` (DigitalOcean NYC3)
- Tailnet: `marlin-tet.ts.net`
- Object storage: Spaces buckets for Loki, Mimir, Tempo, Pyroscope

## Implementation Notes

- Do not use em dashes in generated content
- Keep configurations minimal
- Prefer explicit configuration over clever automation
- Templates use `_template` naming

## Grafana Datasources

| Name | UID | Type |
|------|-----|------|
| `mimir-do-nyc3-prod` | `PDFDDA34E6E7D2823` | prometheus |
| `loki-do-nyc3-prod` | `PF99E8F4CDB5B6FB2` | loki |
| `tempo-do-nyc3-prod` | `P3FE448E25097FAF8` | tempo |

## Quick Reference

| Topic | Documentation |
|-------|---------------|
| Deploy new app | [docs/how-to/deploy-new-app.md](docs/how-to/deploy-new-app.md) |
| Add namespace to Linkerd mesh | [docs/how-to/add-namespace-to-mesh.md](docs/how-to/add-namespace-to-mesh.md) |
| Update Linkerd | [docs/how-to/update-linkerd-edge.md](docs/how-to/update-linkerd-edge.md) |
| Update Terraform providers | [docs/how-to/update-terraform-providers.md](docs/how-to/update-terraform-providers.md) |
| ArgoCD webhooks | [docs/how-to/argocd-webhook-tailscale-funnel.md](docs/how-to/argocd-webhook-tailscale-funnel.md) |
| Tailscale ProxyGroup ingress | [docs/how-to/tailscale-proxygroup-ingress.md](docs/how-to/tailscale-proxygroup-ingress.md) |
| Query logs (LogQL) | [docs/how-to/query-logs.md](docs/how-to/query-logs.md) |

| Component | Reference |
|-----------|-----------|
| External Secrets / 1Password | [docs/reference/external-secrets.md](docs/reference/external-secrets.md) |
| Tailscale Operator | [docs/reference/tailscale-operator.md](docs/reference/tailscale-operator.md) |
| Linkerd | [docs/reference/linkerd.md](docs/reference/linkerd.md) |
| ArgoCD manifests | [docs/reference/argocd-manifests.md](docs/reference/argocd-manifests.md) |
| CloudNativePG backups | [docs/reference/cloudnative-pg-backup.md](docs/reference/cloudnative-pg-backup.md) |
| Grafana datasources | [docs/reference/grafana-datasources.md](docs/reference/grafana-datasources.md) |
| Mimir tenancy | [docs/reference/mimir-tenancy.md](docs/reference/mimir-tenancy.md) |
| Logging architecture | [docs/reference/logging-architecture.md](docs/reference/logging-architecture.md) |
| Tracing architecture | [docs/reference/tracing-architecture.md](docs/reference/tracing-architecture.md) |
| Metrics architecture | [docs/reference/metrics-architecture.md](docs/reference/metrics-architecture.md) |
| Miniflux | [docs/reference/miniflux.md](docs/reference/miniflux.md) |
| n8n | [docs/reference/n8n.md](docs/reference/n8n.md) |

## Documentation

Full docs at [docs/README.md](docs/README.md) following [Divio system](https://documentation.divio.com/):
- `docs/tutorials/` - Learning-oriented guides
- `docs/how-to/` - Task-oriented recipes
- `docs/reference/` - Technical specifications
- `docs/troubleshooting/` - Debugging guides
