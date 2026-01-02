#!/usr/bin/env bash
set -euo pipefail

# Bootstrap ArgoCD on a cluster

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 <cluster-name>"
    echo ""
    echo "Prerequisites:"
    echo "  - kubectl configured for the target cluster"
    echo "  - Helm 3 installed"
    echo ""
    echo "This script will:"
    echo "  1. Create argocd namespace"
    echo "  2. Update Helm dependencies"
    echo "  3. Install ArgoCD via Helm"
    echo "  4. Apply the root ApplicationSet"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

CLUSTER_NAME="$1"
BOOTSTRAP_DIR="$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME/argocd/bootstrap"
APPSET_DIR="$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME/argocd/applicationsets"

# Verify cluster directory exists
if [[ ! -d "$BOOTSTRAP_DIR" ]]; then
    echo "Error: Cluster bootstrap directory not found: $BOOTSTRAP_DIR"
    echo "Run: ./scripts/new-cluster.sh $CLUSTER_NAME"
    exit 1
fi

# Verify kubectl is configured
echo "Verifying kubectl configuration..."
if ! kubectl cluster-info &>/dev/null; then
    echo "Error: kubectl is not configured or cluster is unreachable"
    echo "Configure kubectl for cluster: $CLUSTER_NAME"
    exit 1
fi

CURRENT_CONTEXT=$(kubectl config current-context)
echo "Current kubectl context: $CURRENT_CONTEXT"
echo ""
read -p "Is this the correct cluster? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted"
    exit 1
fi

# Create namespace
echo ""
echo "Creating argocd namespace..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# Update Helm dependencies
echo ""
echo "Updating Helm dependencies..."
cd "$BOOTSTRAP_DIR"
helm dependency update

# Install ArgoCD
echo ""
echo "Installing ArgoCD..."
helm upgrade --install argocd . \
    --namespace argocd \
    --wait \
    --timeout 10m

# Wait for ArgoCD to be ready
echo ""
echo "Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

# Wait for CRDs to be established
echo ""
echo "Waiting for ArgoCD CRDs to be ready..."
kubectl wait --for=condition=Established crd/applications.argoproj.io --timeout=60s
kubectl wait --for=condition=Established crd/applicationsets.argoproj.io --timeout=60s
kubectl wait --for=condition=Established crd/appprojects.argoproj.io --timeout=60s

# Apply ApplicationSet
echo ""
echo "Applying root ApplicationSet..."
kubectl apply -f "$APPSET_DIR/apps.yaml"

# Apply ArgoCD self-management Application
if [[ -f "$APPSET_DIR/argocd.yaml" ]]; then
    echo ""
    echo "Applying ArgoCD self-management Application..."
    kubectl apply -f "$APPSET_DIR/argocd.yaml"
fi

echo ""
echo "ArgoCD bootstrap complete!"
echo ""
echo "Access ArgoCD:"
echo "  URL: https://argocd-$CLUSTER_NAME (via Tailscale)"
echo ""
echo "Get initial admin password:"
echo "  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
echo "Next steps:"
echo "1. Add apps by creating values in kubernetes/clusters/$CLUSTER_NAME/apps/"
echo "2. ArgoCD will automatically detect and deploy them"
