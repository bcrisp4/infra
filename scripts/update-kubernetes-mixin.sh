#!/usr/bin/env bash
set -euo pipefail

# Update kubernetes-mixin rules and dashboards
#
# Usage: ./scripts/update-kubernetes-mixin.sh [VERSION]
# Example: ./scripts/update-kubernetes-mixin.sh 1.4.1
#          ./scripts/update-kubernetes-mixin.sh  # uses default version
#
# This script downloads the kubernetes-mixin release and:
# - Extracts rules and converts to Mimir format (adds namespace key)
# - Extracts dashboards, adds stable UIDs, removes Windows dashboards
#
# After running, you need to:
# 1. Commit and push changes (dashboards deploy via ArgoCD)
# 2. Upload rules to Mimir via mimirtool (see output for command)

VERSION="${1:-1.4.1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

# Cross-platform MD5 hash function (works on macOS and Linux)
md5hash() {
  if command -v md5sum &> /dev/null; then
    # Linux: md5sum outputs "hash  -"
    md5sum | cut -d' ' -f1
  else
    # macOS: md5 -q outputs just the hash
    md5 -q
  fi
}

echo "==> Downloading kubernetes-mixin version $VERSION..."
curl -sL "https://github.com/kubernetes-monitoring/kubernetes-mixin/releases/download/version-${VERSION}/kubernetes-mixin-version-${VERSION}.zip" \
  -o "$TMP_DIR/k8s-mixin.zip"

# --- Rules ---
echo "==> Extracting and converting rules for Mimir..."
mkdir -p "$REPO_ROOT/kubernetes/apps/mimir/files"
{
  echo "namespace: kubernetes-mixin"
  unzip -p "$TMP_DIR/k8s-mixin.zip" prometheus_rules.yaml
} > "$REPO_ROOT/kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml"

# --- Dashboards ---
echo "==> Extracting dashboards..."
mkdir -p "$TMP_DIR/dashboards"
unzip -j "$TMP_DIR/k8s-mixin.zip" "dashboards_out/*.json" -d "$TMP_DIR/dashboards/"

echo "==> Removing Windows and inaccessible control plane dashboards..."
# Windows dashboards - not applicable
rm -f "$TMP_DIR/dashboards/"*windows*.json
# Control plane dashboards - managed by DigitalOcean, not accessible in DOKS
rm -f "$TMP_DIR/dashboards/scheduler.json"
rm -f "$TMP_DIR/dashboards/controller-manager.json"

echo "==> Adding stable UIDs to dashboards..."
for f in "$TMP_DIR/dashboards/"*.json; do
  name=$(basename "$f" .json)
  # Generate deterministic UID from dashboard name (first 12 chars of MD5)
  uid=$(echo -n "k8s-mixin-$name" | md5hash | cut -c1-12)
  jq --arg uid "$uid" '.uid = $uid' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

echo "==> Copying dashboards to repo..."
mkdir -p "$REPO_ROOT/kubernetes/apps/grafana/dashboards/kubernetes-mixin"
cp "$TMP_DIR/dashboards/"*.json "$REPO_ROOT/kubernetes/apps/grafana/dashboards/kubernetes-mixin/"

echo ""
echo "Done! Files updated:"
echo "  - kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml"
echo "  - kubernetes/apps/grafana/dashboards/kubernetes-mixin/*.json"
echo ""
echo "Dashboards extracted:"
ls -1 "$REPO_ROOT/kubernetes/apps/grafana/dashboards/kubernetes-mixin/"
echo ""
echo "Next steps:"
echo "  1. Commit and push changes (dashboards deploy via ArgoCD)"
echo "  2. Upload rules to Mimir:"
echo "     kubectl port-forward -n mimir svc/mimir-gateway 8080:80 &"
echo "     mimirtool rules sync --address=http://localhost:8080 --id=prod \\"
echo "       kubernetes/apps/mimir/files/kubernetes-mixin-rules.yaml"
echo "     kill %1"
