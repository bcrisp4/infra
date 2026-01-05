# Mimir Multi-Tenancy

Reference for Mimir tenant configuration and the tenant endpoint.

## Overview

Mimir requires the `X-Scope-OrgID` header for multi-tenancy. The current tenant is `prod`.

## How Clients Set Tenant

| Client | Method |
|--------|--------|
| Grafana | `secureJsonData.httpHeaderValue1: prod` in datasource config |
| otel-metrics | `headers: X-Scope-OrgID: prod` in OTLP exporter |
| linkerd-viz | Via gateway's `/tenant/prod/` path (cannot set headers directly) |

## Tenant Endpoint

Some clients (like linkerd-viz) cannot set custom HTTP headers. For these clients, use the gateway's tenant endpoint.

### How It Works

The Mimir gateway nginx is configured with a `/tenant/{tenant}/` path that adds the `X-Scope-OrgID` header before forwarding to internal Mimir components.

```
Client (no header support)
    |
    v
mimir-gateway/tenant/prod/ (adds X-Scope-OrgID: prod)
    |
    v
Mimir query components
```

### Configuration

Add serverSnippet to the gateway in cluster values:

```yaml
# kubernetes/clusters/{cluster}/apps/mimir/values.yaml
mimir-distributed:
  gateway:
    nginx:
      config:
        serverSnippet: |
          location /tenant/prod/ {
            proxy_pass http://localhost:8080/;
            proxy_set_header X-Scope-OrgID prod;
            proxy_http_version 1.1;
          }
```

### Usage Example: linkerd-viz

```yaml
# kubernetes/clusters/{cluster}/apps/linkerd-viz/values.yaml
linkerd-viz:
  prometheus:
    enabled: false
  prometheusUrl: http://mimir-gateway.mimir.svc.cluster.local/tenant/prod/prometheus
```

## Direct API Access

For direct queries to Mimir (requires X-Scope-OrgID header):

```bash
curl -H "X-Scope-OrgID: prod" \
  "http://mimir-gateway.mimir.svc.cluster.local/prometheus/api/v1/query?query=up"
```

## Related

- [Metrics Architecture](metrics-architecture.md)
- [Grafana Datasources](grafana-datasources.md)
