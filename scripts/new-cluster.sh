#!/usr/bin/env bash
set -euo pipefail

# Create a new cluster from templates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 <cluster-name>"
    echo ""
    echo "Cluster name format: {provider}-{region}-{env}"
    echo "Examples:"
    echo "  htz-fsn1-prod    # Hetzner Falkenstein production"
    echo "  do-nyc1-dev      # DigitalOcean NYC development"
    echo "  aws-eu-west-1-stg # AWS Ireland staging"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

CLUSTER_NAME="$1"

# Validate cluster name format
if [[ ! "$CLUSTER_NAME" =~ ^[a-z]+-[a-z0-9]+-[a-z]+$ ]]; then
    echo "Error: Invalid cluster name format"
    echo "Expected: {provider}-{region}-{env}"
    exit 1
fi

# Parse cluster name components
PROVIDER="${CLUSTER_NAME%%-*}"
REGION="${CLUSTER_NAME#*-}"
REGION="${REGION%-*}"
ENV="${CLUSTER_NAME##*-}"

echo "Creating cluster: $CLUSTER_NAME"
echo "  Provider: $PROVIDER"
echo "  Region: $REGION"
echo "  Environment: $ENV"
echo ""

# Check if cluster already exists
if [[ -d "$REPO_ROOT/terraform/clusters/$CLUSTER_NAME" ]]; then
    echo "Error: Terraform cluster directory already exists"
    exit 1
fi

if [[ -d "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" ]]; then
    echo "Error: Kubernetes cluster directory already exists"
    exit 1
fi

# Create Terraform cluster directory
echo "Creating Terraform configuration..."
cp -r "$REPO_ROOT/terraform/clusters/_template" "$REPO_ROOT/terraform/clusters/$CLUSTER_NAME"

# Update placeholders in Terraform files
sed -i.bak "s/{{cluster_name}}/$CLUSTER_NAME/g" "$REPO_ROOT/terraform/clusters/$CLUSTER_NAME"/*.tf
sed -i.bak "s/{{cluster_name}}/$CLUSTER_NAME/g" "$REPO_ROOT/terraform/clusters/$CLUSTER_NAME"/*.example
rm -f "$REPO_ROOT/terraform/clusters/$CLUSTER_NAME"/*.bak

# Create Kubernetes cluster directory
echo "Creating Kubernetes configuration..."
cp -r "$REPO_ROOT/kubernetes/clusters/_template" "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME"

# Update placeholders in Kubernetes files
find "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" -type f -name "*.yaml" -exec sed -i.bak "s/{{cluster_name}}/$CLUSTER_NAME/g" {} \;
find "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" -type f -name "*.yaml" -exec sed -i.bak "s/{{provider}}/$PROVIDER/g" {} \;
find "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" -type f -name "*.yaml" -exec sed -i.bak "s/{{region}}/$REGION/g" {} \;
find "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" -type f -name "*.yaml" -exec sed -i.bak "s/{{env}}/$ENV/g" {} \;
find "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" -type f -name "*.bak" -delete

# Update README
sed -i.bak "s/{{cluster_name}}/$CLUSTER_NAME/g" "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME/README.md"
rm -f "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME/README.md.bak"

echo ""
echo "Cluster scaffolding complete!"
echo ""
echo "Next steps:"
echo "1. Add cluster to terraform/global/terraform.tfvars:"
echo "   clusters = {"
echo "     \"$CLUSTER_NAME\" = { tags = [\"$CLUSTER_NAME\"] }"
echo "   }"
echo ""
echo "2. Apply global Terraform to create Tailscale auth key"
echo ""
echo "3. Create Terraform Cloud workspace: $CLUSTER_NAME"
echo ""
echo "4. Configure terraform/clusters/$CLUSTER_NAME/terraform.tfvars"
echo ""
echo "5. Add provider module and apply Terraform"
echo ""
echo "6. Bootstrap ArgoCD:"
echo "   ./scripts/bootstrap-argocd.sh $CLUSTER_NAME"
