# Why We Use Linkerd Edge Releases

This document explains why this infrastructure uses Linkerd edge releases instead of stable releases.

## Background

Linkerd offers two release channels:
- **Stable:** Versioned releases (e.g., 2.14.0) with semantic versioning
- **Edge:** Monthly releases (e.g., edge-25.12.3) with continuous updates

## Why Edge?

### 1. Open-source stable releases stopped

Buoyant (the company behind Linkerd) stopped publishing open-source stable releases after version 2.14 in February 2024. Stable releases now require a Buoyant Enterprise subscription.

Edge releases remain fully open-source and free to use.

### 2. Native sidecar support

Edge releases include native sidecar support (Kubernetes 1.29+), which fixes a critical issue: **Jobs with Linkerd sidecars never complete** because the proxy container keeps running after the main container exits.

With native sidecars enabled (`proxy.nativeSidecar: true`), Kubernetes properly manages the sidecar lifecycle.

### 3. All bugfixes and security patches

Edge releases receive all bugfixes and security patches. Since stable releases are no longer published, edge is the only way to get fixes for the open-source version.

## Version Format

Edge releases use: `edge-YY.MM.N`

- `YY` - Year (e.g., 25 for 2025)
- `MM` - Month
- `N` - Patch number within the month

Example: `edge-25.12.3` is the 3rd patch release in December 2025.

## Risks and Mitigation

### Edge releases are not semantically versioned

Breaking changes can occur in any release. To mitigate:

1. **Check release notes** before upgrading
2. **Skip "not recommended" releases** marked on GitHub
3. **Read monthly roundups** on the Linkerd blog
4. **Use pessimistic version constraints** (`~2025.12`) to limit upgrades to patch releases within a month

### No LTS or extended support

Each edge release is only supported until the next release. Keep up with monthly updates.

## Key Resources

- **Release notes:** https://github.com/linkerd/linkerd2/releases
- **Monthly roundups:** https://linkerd.io/blog/ (search "Edge Release Roundup")
- **Upgrade guide:** https://linkerd.io/2-edge/tasks/upgrade/

## Related

- [Linkerd Reference](../reference/linkerd.md)
- [Update Linkerd Edge](../how-to/update-linkerd-edge.md)
