# Tutorial: Deploy Your First App

This tutorial walks you through deploying an application to a cluster using the GitOps workflow.

## What You'll Learn

- How apps are structured in this repository
- How to create an umbrella Helm chart
- How to configure cluster-specific values
- How ArgoCD auto-discovers and deploys apps

## Prerequisites

- A running cluster with ArgoCD (see [Add a New Cluster](add-new-cluster.md))
- Helm CLI installed
- kubectl configured for your cluster
- Git access to push changes

## Overview

Apps in this infrastructure follow a two-layer structure:

1. **App definition** (`kubernetes/apps/<app>/`) - The umbrella Helm chart wrapping an upstream chart
2. **Cluster config** (`kubernetes/clusters/<cluster>/apps/<app>/`) - Cluster-specific settings

ArgoCD watches for new cluster configs and automatically deploys matching apps.

## Step 1: Choose an Application

For this tutorial, we'll deploy [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics), a simple application that exposes Kubernetes metrics.

First, find the chart:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm search repo prometheus-community/kube-state-metrics --versions | head -5
```

You should see available versions. Note the latest version number.

## Step 2: Create the App Definition

Create the directory structure:

```bash
mkdir -p kubernetes/apps/kube-state-metrics/templates
```

Create the Chart.yaml:

```yaml
# kubernetes/apps/kube-state-metrics/Chart.yaml
apiVersion: v2
name: kube-state-metrics
version: 1.0.0
description: Umbrella chart for kube-state-metrics
dependencies:
  - name: kube-state-metrics
    version: "~5.27"  # Use the version you found
    repository: https://prometheus-community.github.io/helm-charts
```

Create base values (shared across all clusters):

```yaml
# kubernetes/apps/kube-state-metrics/values.yaml
kube-state-metrics:
  # Reasonable resource limits
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
    limits:
      memory: 128Mi

  # Enable Prometheus scraping
  prometheusScrape: true
```

Download the chart dependencies:

```bash
cd kubernetes/apps/kube-state-metrics
helm dependency update
cd ../../..
```

## Step 3: Create Cluster Config

Now tell ArgoCD to deploy this app to your cluster.

Create the cluster-specific directory:

```bash
mkdir -p kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics
```

Create the config.yaml (required for ArgoCD to discover the app):

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics/config.yaml
name: kube-state-metrics
```

Create cluster-specific values (optional overrides):

```yaml
# kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics/values.yaml
kube-state-metrics:
  # No overrides needed for this simple app
  {}
```

## Step 4: Commit and Push

```bash
git add kubernetes/apps/kube-state-metrics kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics
git commit -m "Add kube-state-metrics application"
git push
```

## Step 5: Watch ArgoCD Deploy

Within a few minutes, ArgoCD will discover the new app config and create an Application.

Check ArgoCD (via CLI or UI):

```bash
# Wait for app to appear
argocd app list | grep kube-state-metrics

# Check sync status
argocd app get kube-state-metrics
```

Or watch the pods:

```bash
kubectl get pods -n kube-state-metrics -w
```

## Step 6: Verify the Deployment

Once deployed, verify it's working:

```bash
# Check pods are running
kubectl get pods -n kube-state-metrics

# Check the metrics endpoint
kubectl port-forward -n kube-state-metrics svc/kube-state-metrics-kube-state-metrics 8080:8080 &
curl localhost:8080/metrics | head -20
```

You should see Prometheus-format metrics about your Kubernetes objects.

## What Just Happened?

1. You created an **umbrella chart** that wraps the upstream kube-state-metrics chart
2. You created a **config.yaml** that tells ArgoCD "deploy this app to this cluster"
3. ArgoCD's **ApplicationSet** detected the new config.yaml via its Git files generator
4. ArgoCD created an **Application** and synced it to the cluster
5. Helm rendered the templates and Kubernetes created the resources

## Next Steps

- Add Linkerd to the app: [Add Namespace to Mesh](../how-to/add-namespace-to-mesh.md)
- Deploy a more complex app with custom templates
- Configure secrets using External Secrets Operator

## Cleanup

To remove the app:

```bash
# Delete the cluster config (ArgoCD will remove the app)
rm -rf kubernetes/clusters/do-nyc3-prod/apps/kube-state-metrics
git add -A
git commit -m "Remove kube-state-metrics from do-nyc3-prod"
git push
```

## Related

- [Deploy a New App](../how-to/deploy-new-app.md) - Detailed reference
- [Architecture Overview](../reference/architecture.md)
