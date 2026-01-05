# ArgoCD Manifests

Reference for ArgoCD Application and ApplicationSet patterns used in this infrastructure.

## Directory Structure

The `argocd/manifests/` directory contains:
- `argocd.yaml` - Application for ArgoCD self-management
- `apps.yaml` - ApplicationSet for cluster app discovery

## Testing Locally

Before pushing changes:

```bash
# Validate YAML syntax (catches structural errors)
yq eval '.' kubernetes/clusters/*/argocd/manifests/*.yaml > /dev/null

# Dry-run with kubectl (validates K8s schema)
kubectl apply --dry-run=client -f kubernetes/clusters/*/argocd/manifests/*.yaml
```

## Go Template Limitations

- Go templates only work on **string fields**, not object fields
- Control structures (`{{- range }}`, `{{- if }}`) break YAML parsing when used directly in templates
- Use `templatePatch` for conditional configuration (supports full Go templating)

## Per-App Namespace Configuration

Apps use `config.yaml` files that the ApplicationSet reads via Git files generator:

```yaml
# kubernetes/clusters/{cluster}/apps/{app}/config.yaml
name: my-app
namespaceLabels:
  example.com/team: platform  # Optional: adds labels to app namespace
namespaceAnnotations:
  linkerd.io/inject: enabled  # Optional: adds annotations to app namespace
```

The `templatePatch` conditionally applies these to `managedNamespaceMetadata`. This works because `templatePatch` is a string field that gets Go template processing before being applied as a patch.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `yaml: line X: could not find expected ':'` | Template control structures at wrong indentation or outside templatePatch | Move templates inside templatePatch |
| Duplicate name errors with literal `{{ ... }}` | Backtick escaping incorrectly added | Remove backticks - YAML is applied directly, not via Helm |

## ApplicationSet Git Files Generator

The ApplicationSet discovers apps by scanning for `config.yaml` files:

```yaml
generators:
  - git:
      repoURL: https://github.com/org/infra.git
      revision: HEAD
      files:
        - path: "kubernetes/clusters/do-nyc3-prod/apps/*/config.yaml"
```

Each `config.yaml` provides template variables for the Application.

## Related

- [ArgoCD Troubleshooting](../troubleshooting/argocd.md)
- [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md)
