#!/usr/bin/env bash
set -euo pipefail

# Create a new application from template

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
    echo "Usage: $0 <app-name> [cluster-name]"
    echo ""
    echo "Arguments:"
    echo "  app-name      Name of the application"
    echo "  cluster-name  Optional: Create cluster-specific values"
    echo ""
    echo "Examples:"
    echo "  $0 grafana                    # Create app definition only"
    echo "  $0 grafana htz-fsn1-prod      # Create app + cluster values"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

APP_NAME="$1"
CLUSTER_NAME="${2:-}"

# Check if app already exists
if [[ -d "$REPO_ROOT/kubernetes/apps/$APP_NAME" ]]; then
    echo "App directory already exists: kubernetes/apps/$APP_NAME"
else
    echo "Creating app: $APP_NAME"
    cp -r "$REPO_ROOT/kubernetes/apps/_template" "$REPO_ROOT/kubernetes/apps/$APP_NAME"

    # Update placeholders
    sed -i.bak "s/{{app_name}}/$APP_NAME/g" "$REPO_ROOT/kubernetes/apps/$APP_NAME"/*.yaml
    sed -i.bak "s/{{app_name}}/$APP_NAME/g" "$REPO_ROOT/kubernetes/apps/$APP_NAME/README.md"
    rm -f "$REPO_ROOT/kubernetes/apps/$APP_NAME"/*.bak

    echo "Created kubernetes/apps/$APP_NAME/"
fi

# Create cluster-specific values if cluster name provided
if [[ -n "$CLUSTER_NAME" ]]; then
    CLUSTER_APP_DIR="$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME/apps/$APP_NAME"

    if [[ ! -d "$REPO_ROOT/kubernetes/clusters/$CLUSTER_NAME" ]]; then
        echo "Error: Cluster directory does not exist: kubernetes/clusters/$CLUSTER_NAME"
        echo "Run: ./scripts/new-cluster.sh $CLUSTER_NAME"
        exit 1
    fi

    if [[ -d "$CLUSTER_APP_DIR" ]]; then
        echo "Cluster app values already exist: kubernetes/clusters/$CLUSTER_NAME/apps/$APP_NAME"
    else
        mkdir -p "$CLUSTER_APP_DIR"
        cat > "$CLUSTER_APP_DIR/values.yaml" <<EOF
# Cluster-specific values for $APP_NAME on $CLUSTER_NAME
# These override values from kubernetes/apps/$APP_NAME/values.yaml

# $APP_NAME:
#   ingress:
#     hosts:
#       - $APP_NAME.$CLUSTER_NAME.example.com
EOF
        echo "Created kubernetes/clusters/$CLUSTER_NAME/apps/$APP_NAME/values.yaml"
    fi
fi

echo ""
echo "Next steps:"
echo "1. Edit kubernetes/apps/$APP_NAME/Chart.yaml to add upstream chart dependency"
echo "2. Edit kubernetes/apps/$APP_NAME/values.yaml with base configuration"
echo "3. Run: cd kubernetes/apps/$APP_NAME && helm dependency update"
if [[ -n "$CLUSTER_NAME" ]]; then
    echo "4. Edit kubernetes/clusters/$CLUSTER_NAME/apps/$APP_NAME/values.yaml"
    echo "5. ArgoCD will automatically deploy the app"
else
    echo "4. To deploy to a cluster, run: $0 $APP_NAME <cluster-name>"
fi
