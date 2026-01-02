# Kubernetes Cluster Template

Template for configuring a new Kubernetes cluster with ArgoCD.

## Structure

```
do-nyc3-prod/
├── argocd/
│   ├── bootstrap/           # ArgoCD installation Helm chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   ├── charts/          # Downloaded chart dependencies
│   │   └── templates/
│   │       └── projects/
│   │           └── default.yaml
│   └── applicationsets/
│       └── apps.yaml        # Root ApplicationSet for app discovery
├── apps/                    # Cluster-specific app value overrides
│   └── .gitkeep
├── cluster.yaml             # Cluster metadata
└── README.md
```

## Setup Instructions

### 1. Create Cluster Directory

```bash
cp -r _template ../do-nyc3-prod
cd ../do-nyc3-prod
```

### 2. Update Cluster Metadata

Edit `cluster.yaml` with your cluster details.

### 3. Update ArgoCD Configuration

Edit `argocd/bootstrap/values.yaml`:
- Update `cluster.name` to `do-nyc3-prod`
- Update Tailscale ingress hostname
- Adjust resource limits as needed

### 4. Update ApplicationSet

Edit `argocd/applicationsets/apps.yaml`:
- Replace `do-nyc3-prod` with actual cluster name in directory path

### 5. Download ArgoCD Chart

```bash
cd argocd/bootstrap
helm dependency update
```

### 6. Bootstrap ArgoCD

```bash
# Ensure kubectl is configured for the cluster
kubectl create namespace argocd
helm install argocd . -n argocd

# Or use the helper script
../../scripts/bootstrap-argocd.sh do-nyc3-prod
```

### 7. Add Applications

To deploy an app to this cluster:

1. Ensure the app exists in `kubernetes/apps/{{app_name}}/`
2. Create cluster-specific values: `mkdir -p apps/{{app_name}}`
3. Add `apps/{{app_name}}/values.yaml` with overrides
4. ArgoCD will automatically detect and deploy it

## Adding Apps

Create a values override file for each app you want to deploy:

```bash
mkdir -p apps/grafana
cat > apps/grafana/values.yaml <<EOF
grafana:
  ingress:
    hosts:
      - grafana.do-nyc3-prod.example.com
EOF
```

The ApplicationSet will automatically discover and deploy apps that have a values file in `apps/`.
