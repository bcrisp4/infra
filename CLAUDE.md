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
helm template test kubernetes/apps/<app> -f kubernetes/clusters/<cluster>/apps/<app>/values.yaml  # Validate templates
```

## Architecture

Infrastructure monorepo for multi-cluster Kubernetes with GitOps. See [docs/reference/architecture.md](docs/reference/architecture.md).

**Terraform:** `bootstrap/` (TFC workspaces) | `global/` (cross-cluster) | `clusters/{cluster}/` (per-cluster)

**Kubernetes:** `apps/{app}/` (Helm charts) | `clusters/{cluster}/apps/{app}/` (config.yaml + values.yaml)
- Umbrella charts (prometheus, grafana, loki) wrap upstream charts via `Chart.yaml` dependencies
- Custom charts (miniflux, thanos) use pure templates with no dependencies

**Patterns:**
- Cluster naming: `{provider}-{region}-{env}` (e.g., `do-nyc3-prod`)
- Apps auto-deploy when `config.yaml` + `values.yaml` added to cluster
- ArgoCD uses the `name` field from `config.yaml` as the Helm release name (affects service DNS names)

## Current State

- Active cluster: `do-nyc3-prod` (DigitalOcean NYC3)
- Tailnet: `marlin-tet.ts.net`
- Object storage: Spaces buckets for Loki, Thanos

## Implementation Notes

- kube-prometheus-stack uses `kube-prometheus` (not `kube-prometheus-stack`) in resource names: `{release}-kube-prometheus-{component}`
- Tailscale ProxyGroup ingress requires custom templates with `defaultBackend` (charts' built-in ingress uses `rules` which doesn't work)
- Do not use em dashes in generated content
- Keep configurations minimal
- Prefer explicit configuration over clever automation
- Templates use `_template` naming

## Grafana Datasources

| Name | Type |
|------|------|
| `prometheus-do-nyc3-prod` | prometheus |
| `loki-do-nyc3-prod` | loki |
| `thanos-do-nyc3-prod` | prometheus (Thanos) |

## Service URLs (do-nyc3-prod)

| Service | URL |
|---------|-----|
| Prometheus | `http://prometheus-kube-prometheus-prometheus.prometheus.svc.cluster.local:9090` |
| Alertmanager | `http://prometheus-kube-prometheus-alertmanager.prometheus.svc.cluster.local:9093` |
| Loki Gateway | `http://loki-gateway.loki.svc.cluster.local` |
| Thanos Query | `http://thanos-query.thanos.svc.cluster.local:10902` |

## Quick Reference

| Topic | Documentation |
|-------|---------------|
| Deploy new app | [docs/how-to/deploy-new-app.md](docs/how-to/deploy-new-app.md) |
| Update Terraform providers | [docs/how-to/update-terraform-providers.md](docs/how-to/update-terraform-providers.md) |
| ArgoCD webhooks | [docs/how-to/argocd-webhook-tailscale-funnel.md](docs/how-to/argocd-webhook-tailscale-funnel.md) |
| Tailscale ProxyGroup ingress | [docs/how-to/tailscale-proxygroup-ingress.md](docs/how-to/tailscale-proxygroup-ingress.md) |
| Query logs (LogQL) | [docs/how-to/query-logs.md](docs/how-to/query-logs.md) |

| Component | Reference |
|-----------|-----------|
| External Secrets / 1Password | [docs/reference/external-secrets.md](docs/reference/external-secrets.md) |
| Tailscale Operator | [docs/reference/tailscale-operator.md](docs/reference/tailscale-operator.md) |
| ArgoCD manifests | [docs/reference/argocd-manifests.md](docs/reference/argocd-manifests.md) |
| CloudNativePG backups | [docs/reference/cloudnative-pg-backup.md](docs/reference/cloudnative-pg-backup.md) |
| Grafana datasources | [docs/reference/grafana-datasources.md](docs/reference/grafana-datasources.md) |
| Logging architecture | [docs/reference/logging-architecture.md](docs/reference/logging-architecture.md) |
| Metrics architecture | [docs/reference/metrics-architecture.md](docs/reference/metrics-architecture.md) |
| Miniflux | [docs/reference/miniflux.md](docs/reference/miniflux.md) |

## Documentation

Full docs at [docs/README.md](docs/README.md) following [Divio system](https://documentation.divio.com/):
- `docs/tutorials/` - Learning-oriented guides
- `docs/how-to/` - Task-oriented recipes
- `docs/reference/` - Technical specifications
- `docs/troubleshooting/` - Debugging guides
