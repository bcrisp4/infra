# Telemetry Correlation Plan

Enable seamless navigation between metrics, logs, and traces in Grafana.

## Current State

**Working:**
- Trace to Logs (basic): filterByTraceID/filterBySpanID enabled
- Trace to Metrics: basic link configured
- Service Map: Tempo metrics generator writing to Mimir

**Missing:**
- Logs to Traces: no derived fields to extract traceID and link to Tempo
- Trace to Logs tag mapping: trace attributes not mapped to Loki labels
- Pre-built metric queries: tracesToMetrics lacks useful query templates

## Implementation Steps

### Step 1: Improve Trace-to-Logs with Tag Mapping

**File:** `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml`

Replace current `tracesToLogs` with enhanced `tracesToLogsV2`:

```yaml
tracesToLogsV2:
  datasourceUid: PF99E8F4CDB5B6FB2
  spanStartTimeShift: '-5m'
  spanEndTimeShift: '5m'
  tags:
    - key: 'k8s.namespace.name'
      value: 'k8s_namespace_name'
    - key: 'k8s.pod.name'
      value: 'k8s_pod_name'
    - key: 'k8s.container.name'
      value: 'k8s_container_name'
    - key: 'k8s.deployment.name'
      value: 'k8s_deployment_name'
    - key: 'service.name'
      value: 'service_name'
  filterByTraceID: true
  filterBySpanID: true
```

**Why:** When clicking from trace to logs, Grafana will construct a LogQL query using mapped labels (e.g., `{k8s_namespace_name="argocd"}`) instead of just time-based filtering.

### Step 2: Enable Logs-to-Traces via Derived Fields

**File:** `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml`

Add `derivedFields` to Loki datasource to extract traceID from log content:

```yaml
derivedFields:
  - datasourceUid: P3FE448E25097FAF8
    matcherRegex: 'trace[_-]?[iI][dD][=:]\\s*"?([a-f0-9]{32})"?'
    name: TraceID
    url: '$${__value.raw}'
    urlDisplayLabel: 'View Trace'
```

**Caveat:** Only works when applications include traceID in log messages. The OTel log protocol sends trace context as structured metadata, but derived fields match against log line content.

### Step 3: Add Trace-to-Metrics Query Templates

**File:** `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml`

Enhance `tracesToMetrics` with pre-built queries using Tempo's span metrics:

```yaml
tracesToMetrics:
  datasourceUid: PDFDDA34E6E7D2823
  spanStartTimeShift: '-5m'
  spanEndTimeShift: '5m'
  tags:
    - key: 'service.name'
      value: 'service'
  queries:
    - name: 'Request Rate'
      query: 'sum(rate(traces_spanmetrics_calls_total{$$__tags}[5m]))'
    - name: 'Error Rate'
      query: 'sum(rate(traces_spanmetrics_calls_total{$$__tags,status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_spanmetrics_calls_total{$$__tags}[5m]))'
    - name: 'Latency (p95)'
      query: 'histogram_quantile(0.95, sum(rate(traces_spanmetrics_latency_bucket{$$__tags}[5m])) by (le))'
```

### Step 4: Create Correlation Reference Doc

**File:** `docs/reference/telemetry-correlation.md` (new)

Document:
- How correlation works between metrics, logs, and traces
- Available correlation links and their requirements
- Label/attribute mappings used

### Step 5: Create App Instrumentation Guide

**File:** `docs/how-to/add-trace-context-to-logs.md` (new)

Document how applications can include traceID/spanID in logs for full logs-to-traces correlation:
- OTel SDK log bridge patterns (Go, Node.js, Python, Java)
- Example structured log formats that work with derived fields
- Testing instructions

### Step 6: Update CLAUDE.md

Add summary of correlation features to the Grafana Datasources section for quick reference.

## Files to Modify

1. `kubernetes/clusters/do-nyc3-prod/apps/grafana/values.yaml` - All datasource correlation config
2. `docs/reference/telemetry-correlation.md` - New reference doc
3. `docs/how-to/add-trace-context-to-logs.md` - New how-to guide for app developers
4. `CLAUDE.md` - Add correlation summary

## Testing

1. **Trace to Logs:** Open Tempo, find trace, click span, verify "Logs" link builds query with namespace/pod labels
2. **Logs to Traces:** Find log with traceID, verify "View Trace" link appears and works
3. **Trace to Metrics:** Click span, verify "Request Rate" etc. queries return span metrics

## Out of Scope

- **Exemplars (Metrics to Traces):** Requires application instrumentation to emit exemplars with traceID. Current span metrics from Tempo don't include exemplars.
- **Automatic trace context in logs:** Would require OTel collector changes or app instrumentation. Recommend documenting how apps can log trace context.

## Datasource UIDs

| Datasource | UID |
|------------|-----|
| Mimir | PDFDDA34E6E7D2823 |
| Loki | PF99E8F4CDB5B6FB2 |
| Tempo | P3FE448E25097FAF8 |
