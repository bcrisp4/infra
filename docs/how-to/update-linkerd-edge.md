# Update Linkerd Edge Release

How to upgrade Linkerd to a new edge release.

## Prerequisites

- Access to the Git repository
- Helm CLI installed

## Before Upgrading

### 1. Check for new releases

```bash
helm search repo linkerd-edge/linkerd-control-plane --versions | head -10
```

### 2. Review release notes

- **GitHub releases:** https://github.com/linkerd/linkerd2/releases
- **Monthly roundups:** https://linkerd.io/blog/ (search "Edge Release Roundup")

### 3. Check for "not recommended" warnings

Some edge releases are marked "not recommended" due to known issues. Skip these releases.

## Upgrade Steps

### 1. Update Chart.yaml versions

```yaml
# kubernetes/apps/linkerd/Chart.yaml
dependencies:
  - name: linkerd-crds
    version: "~2025.12"  # Update to new month
    repository: https://helm.linkerd.io/edge
  - name: linkerd-control-plane
    version: "~2025.12"  # Update to new month
    repository: https://helm.linkerd.io/edge
```

### 2. Update dependencies

```bash
cd kubernetes/apps/linkerd && helm dependency update
cd kubernetes/apps/linkerd-viz && helm dependency update
```

### 3. Commit and push

```bash
git add kubernetes/apps/linkerd kubernetes/apps/linkerd-viz
git commit -m "Upgrade Linkerd to edge-25.12.x"
git push
```

### 4. Monitor the rollout

Watch ArgoCD sync the changes and monitor the Linkerd pods:

```bash
kubectl get pods -n linkerd -w
```

## Version Format

Edge releases use: `edge-YY.MM.N` (e.g., `edge-25.12.3`)

Note: Edge releases are NOT semantically versioned. Breaking changes can occur in any release.

## Risk Mitigation

1. Check GitHub releases for "not recommended" labels
2. Read monthly roundup blog posts for known issues
3. Test in non-production first if possible
4. Keep a rollback plan (previous Chart.yaml versions)

## Related

- [Linkerd Edge Releases](../explanation/linkerd-edge-releases.md) - Why we use edge
- [Linkerd Reference](../reference/linkerd.md)
