# Application Template

Template for adding a new application to the infrastructure.

## Structure

```
{{app_name}}/
├── Chart.yaml       # Helm chart with upstream dependency
├── values.yaml      # Base values (shared across all clusters)
├── charts/          # Downloaded chart dependencies (gitignored)
├── templates/       # Custom templates (optional)
│   └── *.yaml
└── README.md
```

## Setup Instructions

### 1. Create App Directory

```bash
cp -r _template ../{{app_name}}
cd ../{{app_name}}
```

### 2. Configure Chart.yaml

Add the upstream chart as a dependency:

```yaml
apiVersion: v2
name: grafana
version: 1.0.0
dependencies:
  - name: grafana
    version: "8.x.x"
    repository: "https://grafana.github.io/helm-charts"
```

### 3. Configure Base Values

Edit `values.yaml` with configuration shared across all clusters.

Values must be namespaced under the dependency name:

```yaml
grafana:  # Matches dependency name in Chart.yaml
  persistence:
    enabled: true
```

### 4. Download Dependencies

```bash
helm dependency update
```

### 5. Deploy to Clusters

For each cluster that should run this app:

```bash
mkdir -p ../../clusters/{{cluster_name}}/apps/{{app_name}}
cat > ../../clusters/{{cluster_name}}/apps/{{app_name}}/values.yaml <<EOF
grafana:
  ingress:
    hosts:
      - grafana.{{cluster_name}}.example.com
EOF
```

ArgoCD will automatically detect and deploy the app.

## Finding Chart Values

To see all available values for an upstream chart:

```bash
helm show values {{chart_repo}}/{{chart_name}}
```

Example:
```bash
helm show values oci://registry-1.docker.io/bitnamicharts/postgresql
helm show values https://grafana.github.io/helm-charts/grafana
```

## Custom Templates

Add custom Kubernetes resources in `templates/`:

```yaml
# templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .Release.Name }}-custom-config
data:
  config.yaml: |
    # Custom configuration
```

## Helm Tips

- Use `helm template . --debug` to test rendering
- Use `helm dependency update` after changing Chart.yaml
- Charts are downloaded to `charts/` (gitignored)
