# Query Logs with LogQL

This guide shows common LogQL queries for exploring logs in Grafana.

## Prerequisites

- Access to Grafana at `https://grafana-do-nyc3-prod.marlin-tet.ts.net`
- The `loki-do-nyc3-prod` datasource is pre-configured

## Basic Queries

### By Namespace

```logql
# All logs from a namespace
{k8s_namespace_name="argocd"}

# Multiple namespaces
{k8s_namespace_name=~"argocd|linkerd"}
```

### By Pod or Deployment

```logql
# Specific pod (use exact pod name)
{k8s_pod_name=~"grafana-.*"}

# All pods in a deployment
{k8s_deployment_name="loki-gateway"}

# StatefulSet pods
{k8s_statefulset_name="loki-ingester"}
```

### By Container

```logql
# Specific container in multi-container pods
{k8s_namespace_name="argocd", k8s_container_name="application-controller"}

# Exclude linkerd-proxy sidecar logs
{k8s_namespace_name="mimir"} != "linkerd-proxy"
```

## Filtering Content

### Text Search

```logql
# Contains text
{k8s_namespace_name="argocd"} |= "error"

# Case insensitive
{k8s_namespace_name="argocd"} |~ "(?i)error"

# Does not contain
{k8s_namespace_name="argocd"} != "health"

# Regex match
{k8s_namespace_name="loki"} |~ "level=(error|warn)"
```

### JSON Logs

```logql
# Parse JSON and filter by field
{k8s_namespace_name="mimir"} | json | level="error"

# Extract specific field
{k8s_namespace_name="argocd"} | json | line_format "{{.msg}}"
```

### Log Levels

The `detected_level` label is auto-populated for many log formats:

```logql
# Error logs only
{k8s_namespace_name="grafana", detected_level="error"}

# Warnings and errors
{k8s_namespace_name="grafana", detected_level=~"error|warn"}
```

## Aggregation Queries

### Count Logs

```logql
# Logs per minute by namespace
sum by (k8s_namespace_name) (count_over_time({log_source="pods"}[1m]))

# Error rate
sum(count_over_time({detected_level="error"}[5m]))
```

### Top Talkers

```logql
# Top 10 pods by log volume
topk(10, sum by (k8s_pod_name) (count_over_time({log_source="pods"}[1h])))
```

## Useful Queries

### Recent Errors Across Cluster

```logql
{cluster="do-nyc3-prod"} |= "error" | json
```

### ArgoCD Sync Events

```logql
{k8s_namespace_name="argocd", k8s_container_name="application-controller"} |= "sync"
```

### Loki Ingestion Errors

```logql
{k8s_namespace_name="loki", k8s_container_name="distributor"} |= "error"
```

### Linkerd Proxy Errors

```logql
{k8s_container_name="linkerd-proxy"} |= "error"
```

### Pod Crashes (OOMKilled, CrashLoopBackOff)

```logql
{k8s_namespace_name="kube-system"} |~ "OOM|CrashLoop|Back-off"
```

## Performance Tips

1. **Always use labels first** - Filter by `k8s_namespace_name` or other labels before text search
2. **Limit time range** - Shorter ranges query faster
3. **Use `|=` over `|~`** - Substring match is faster than regex
4. **Avoid `.*` regex** - Be specific in patterns

## Troubleshooting

### No Logs Returned

1. Check the time range - logs only go back to when otel-logs was deployed
2. Verify namespace exists: `{k8s_namespace_name="your-namespace"}`
3. Check if pods have logs: `kubectl logs -n <namespace> <pod>`

### Slow Queries

1. Add more label filters
2. Reduce time range
3. Use simpler text filters

## Related

- [Logging Architecture](../reference/logging-architecture.md) - System design
- [Grafana Datasources](../reference/grafana-datasources.md) - Datasource configuration
