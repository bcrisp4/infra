# Dependabot

Dependabot automatically creates pull requests to update dependencies. This repository uses Dependabot for both Helm chart dependencies and Terraform providers.

## Configuration

The configuration lives in `.github/dependabot.yml`.

### Ecosystems Configured

| Ecosystem | Directories | What it updates |
|-----------|-------------|-----------------|
| `helm` | `/kubernetes/apps/*` | Chart.yaml dependencies |
| `terraform` | `/terraform/bootstrap`, `/terraform/global`, `/terraform/clusters/*` | Provider versions |

Glob patterns (`*`) automatically discover directories, so new apps and clusters are monitored without config changes.

### Schedule

All ecosystems check for updates weekly on Monday.

### PR Settings

- **Reviewer**: @bcrisp4
- **Labels**: `dependencies`, plus ecosystem-specific (`helm` or `terraform`)

## How It Works

### Helm Charts

Dependabot scans `Chart.yaml` files in `/kubernetes/apps/` for dependencies:

```yaml
dependencies:
  - name: grafana
    version: ~10.4
    repository: https://grafana.github.io/helm-charts
```

When a new version is available, Dependabot creates a PR updating the version constraint.

### Terraform Providers

Dependabot scans `required_providers` blocks in Terraform files:

```hcl
required_providers {
  digitalocean = {
    source  = "digitalocean/digitalocean"
    version = "~> 2.72"
  }
}
```

When a new provider version is released, Dependabot creates a PR updating the version constraint.

## Adding New Directories

### New Cluster (Automatic)

New clusters in `/terraform/clusters/` are automatically discovered via the `*` glob pattern. No configuration changes needed.

### New Top-Level Terraform Directory

If you add a new top-level directory (outside of `clusters/`), add it to the `directories` list in `.github/dependabot.yml`:

```yaml
- package-ecosystem: "terraform"
  directories:
    - "/terraform/bootstrap"
    - "/terraform/global"
    - "/terraform/clusters/*"
    - "/terraform/new-directory"  # Add new directory here
```

### New Helm Chart Location

If Helm charts are moved to a different directory structure, update the `directory` field for the `helm` ecosystem.

## Reviewing Dependabot PRs

1. Check the changelog/release notes linked in the PR
2. Review breaking changes
3. For Terraform: consider running `terraform plan` in TFC to verify
4. For Helm: ArgoCD will show a diff after merge

## Testing the Configuration

### Verify Configuration Is Valid

After pushing, GitHub validates the `dependabot.yml` syntax automatically. Check for errors at:

**Settings > Code security and analysis > Dependabot > View logs**

### Manually Trigger a Check

1. Go to **Insights > Dependency graph > Dependabot** in your repository
2. Click "Check for updates" next to any ecosystem
3. Or wait for the scheduled run (Mondays)

### Verify Dependabot Can Find Dependencies

In the Dependabot logs, you should see:
- For Helm: "Found X dependencies in Chart.yaml"
- For Terraform: "Found X provider requirements"

If you see "dependency_file_not_found", check the directory paths.

### Test with an Outdated Dependency

To verify end-to-end:
1. Temporarily pin a dependency to an older version
2. Trigger a manual check
3. Dependabot should create a PR to update it
4. Close/revert the test PR

## Troubleshooting

### PRs Not Being Created

1. Check the Dependabot logs in GitHub (Settings > Code security > Dependabot)
2. Verify the directory paths are correct
3. For Helm: ensure Chart.yaml has proper `dependencies` section with `repository` field

### OCI Registry Issues

Helm charts from OCI registries (e.g., `oci://ghcr.io/...`) may require additional `registries` configuration. See [GitHub documentation](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/guidance-for-the-configuration-of-private-registries-for-dependabot) for details.

## References

- [Dependabot configuration options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
- [Supported ecosystems](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories)
- [Helm support announcement](https://github.blog/changelog/2025-04-09-dependabot-version-updates-now-support-helm/)
