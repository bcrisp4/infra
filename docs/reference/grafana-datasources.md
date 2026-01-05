# Grafana Datasource Provisioning

Reference for provisioning Grafana datasources via Helm values.

## Overview

Grafana datasources are provisioned via the Helm chart's `datasources` value, which creates a ConfigMap mounted at `/etc/grafana/provisioning/datasources/`.

## Key Pitfalls

### 1. Name is the identifier

Grafana uses datasource `name` as the primary identifier. Changing the name creates a NEW datasource instead of updating the existing one. The old datasource remains in the database.

### 2. Don't use deleteDatasources

The `deleteDatasources` directive crashes Grafana if the datasource to delete doesn't exist:

```
Datasource provisioning error: data source not found
```

Avoid using it - manually delete old datasources via the UI instead.

### 3. Don't use uid for existing datasources

If a datasource already exists without a uid (or with a different uid), adding `uid` to provisioning can cause conflicts and crashes. Only use `uid` for new datasources.

### 4. Datasources persist in database

Even though provisioning is via ConfigMap, Grafana stores datasources in its database (PostgreSQL). The ConfigMap is only read on startup to sync state.

## Example: Mimir/Prometheus Datasource

```yaml
grafana:
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
        - name: mimir-do-nyc3-prod
          type: prometheus
          access: proxy
          url: http://mimir-gateway.mimir.svc.cluster.local/prometheus
          isDefault: true
          editable: false
          jsonData:
            prometheusType: Mimir
            prometheusVersion: 2.9.1
            timeInterval: 30s
            cacheLevel: High
            incrementalQuerying: true
            incrementalQueryOverlapWindow: 10m
            httpHeaderName1: X-Scope-OrgID
          secureJsonData:
            httpHeaderValue1: prod
```

## prometheusVersion Values for Mimir

The version dropdown uses specific values (from Grafana source code):
- `2.0.0` through `2.9.0` for specific minor versions
- `2.9.1` = "> 2.9.x" (use this for Mimir 3.0+)

These are NOT actual Mimir versions - they're Grafana's internal version identifiers that enable specific API features.

## jsonData Fields

| Field | Description |
|-------|-------------|
| `prometheusType` | `Prometheus`, `Mimir`, `Cortex`, or `Thanos` |
| `prometheusVersion` | Version identifier (see above) |
| `timeInterval` | Scrape interval (e.g., `30s`) - should match your scraper config |
| `cacheLevel` | `Low`, `Medium`, `High`, or `None` - higher is better for high cardinality |
| `incrementalQuerying` | `true` to cache query results and only fetch new data |
| `incrementalQueryOverlapWindow` | Overlap window for incremental queries (e.g., `10m`) |
| `httpHeaderName1` / `httpHeaderValue1` | Custom headers (use `secureJsonData` for sensitive values) |

## Renaming a Datasource

If you need to rename a datasource:

1. Update the provisioning config with the new name
2. Deploy and let Grafana create the new datasource
3. Manually delete the old datasource via Grafana UI (Connections > Data sources)
4. Update any dashboards that reference the old datasource name

## Related

- [Mimir Tenancy](mimir-tenancy.md) - Multi-tenant configuration
- [Metrics Architecture](metrics-architecture.md)
