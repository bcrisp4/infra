# Deploy a New App

How to add and deploy a new application to a cluster.

## Prerequisites

- Helm CLI installed
- Access to the Git repository

## Steps

### 1. Find the upstream chart

```bash
# Add the chart repository
helm repo add <name> <url>
helm repo update

# Search for available versions
helm search repo <chart> --versions | head -5

# View all available values
helm show values <repo>/<chart>
```

### 2. Create the umbrella chart

Create the app directory structure:

```bash
./scripts/new-app.sh <app-name>
# Or manually:
mkdir -p kubernetes/apps/<app-name>/templates
```

Create `Chart.yaml` with the upstream dependency:

```yaml
# kubernetes/apps/<app>/Chart.yaml
apiVersion: v2
name: <app-name>
version: 1.0.0
dependencies:
  - name: <chart-name>
    version: "~X.Y"  # Pessimistic constraint
    repository: "https://charts.example.com"
```

### 3. Create base values

Create `values.yaml` with shared configuration:

```yaml
# kubernetes/apps/<app>/values.yaml
<chart-name>:  # Must match dependency name
  # Base values shared across all clusters
  resources:
    requests:
      memory: 128Mi
      cpu: 100m
```

### 4. Download chart dependencies

```bash
cd kubernetes/apps/<app>
helm dependency update
```

### 5. Create cluster config

Create the config for each cluster that should run this app:

```yaml
# kubernetes/clusters/{cluster}/apps/<app>/config.yaml
name: <app-name>
namespace: <app-name>  # Optional: defaults to name
namespaceLabels: {}    # Optional
namespaceAnnotations:  # Optional
  linkerd.io/inject: enabled  # Add to mesh
```

```yaml
# kubernetes/clusters/{cluster}/apps/<app>/values.yaml
<chart-name>:
  # Cluster-specific overrides
  replicas: 2
```

### 6. Commit and push

```bash
git add kubernetes/apps/<app> kubernetes/clusters/*/apps/<app>
git commit -m "Add <app-name> application"
git push
```

### 7. Verify deployment

ArgoCD will auto-discover and deploy the app within a few minutes.

```bash
# Check ArgoCD detected the app
argocd app list | grep <app-name>

# Check pods are running
kubectl get pods -n <app-name>
```

## Values Namespacing

Values in cluster overrides must be namespaced under the dependency name:

```yaml
# Correct
external-secrets:
  resources:
    limits:
      memory: 256Mi

# Wrong - won't apply
resources:
  limits:
    memory: 256Mi
```

## Adding Custom Templates

To add custom resources alongside the upstream chart, create templates in `kubernetes/apps/<app>/templates/`:

```yaml
# kubernetes/apps/<app>/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-custom-config
data:
  config.yaml: |
    # Custom configuration
```

## Related

- [Architecture Overview](../reference/architecture.md)
- [Add Namespace to Mesh](add-namespace-to-mesh.md) - Enable Linkerd for the app
