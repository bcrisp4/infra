# Query Kubernetes Events

Query Kubernetes events stored in Loki using LogQL.

## Prerequisites

- Access to Grafana (`grafana-do-nyc3-prod.marlin-tet.ts.net`)
- `loki-do-nyc3-prod` datasource configured

## Basic Queries

### All Cluster Events

```logql
{log_source="events"}
```

### Events by Namespace

```logql
{log_source="events"} | json | k8s_namespace_name="argocd"
```

### Events by Object Type

```logql
# Pod events
{log_source="events"} | json | k8s_object_kind="Pod"

# Deployment events
{log_source="events"} | json | k8s_object_kind="Deployment"

# Node events
{log_source="events"} | json | k8s_object_kind="Node"
```

### Events by Reason

Common event reasons:

| Reason | Description |
|--------|-------------|
| `Scheduled` | Pod scheduled to a node |
| `Pulled` | Container image pulled |
| `Created` | Container created |
| `Started` | Container started |
| `Killing` | Container being terminated |
| `FailedScheduling` | Pod could not be scheduled |
| `BackOff` | Container restarting with backoff |
| `Unhealthy` | Liveness/readiness probe failed |
| `ScalingReplicaSet` | ReplicaSet scaling |

```logql
# Scheduling events
{log_source="events"} | json | k8s_event_reason="Scheduled"

# Failed scheduling
{log_source="events"} | json | k8s_event_reason="FailedScheduling"

# Container backoff (crash loops)
{log_source="events"} | json | k8s_event_reason="BackOff"

# Probe failures
{log_source="events"} | json | k8s_event_reason="Unhealthy"
```

### Warning Events

```logql
# All warnings (searching in body)
{log_source="events"} |= "Warning"

# Warnings in specific namespace
{log_source="events"} | json | k8s_namespace_name="mimir" |= "Warning"
```

### Events for Specific Pod

```logql
{log_source="events"} | json | k8s_object_name="grafana-0"
```

### Events on Specific Node

```logql
{log_source="events"} | json | k8s_node_name="workers-8vcpu-16gb-5v4we"
```

## Advanced Queries

### Failed Events (Multiple Reasons)

```logql
{log_source="events"} | json | k8s_event_reason=~"Failed.*|BackOff|Unhealthy|Error.*"
```

### Recent Scaling Events

```logql
{log_source="events"} | json | k8s_event_reason=~"ScalingReplicaSet|SuccessfulRescale"
```

### Events with High Count (Repeated Issues)

Events that occur frequently often indicate ongoing problems:

```logql
{log_source="events"} | json | k8s_event_count > 5
```

### Image Pull Events

```logql
{log_source="events"} | json | k8s_event_reason=~"Pull.*|ErrImagePull|ImagePullBackOff"
```

### Volume Events

```logql
{log_source="events"} | json | k8s_event_reason=~".*Volume.*|.*Mount.*|.*Attach.*"
```

## Event Attributes

Events include the following attributes (available after `| json`):

| Attribute | Description |
|-----------|-------------|
| `k8s_event_reason` | Event reason (Scheduled, Pulled, Failed, etc.) |
| `k8s_event_action` | Event action |
| `k8s_event_name` | Event resource name |
| `k8s_event_uid` | Event UID |
| `k8s_event_count` | Number of times event occurred |
| `k8s_namespace_name` | Namespace where event occurred |
| `k8s_object_kind` | Kind of involved object (Pod, Deployment, etc.) |
| `k8s_object_name` | Name of involved object |
| `k8s_node_name` | Node name (if applicable) |

## Troubleshooting Examples

### Why Won't My Pod Schedule?

```logql
{log_source="events"} | json | k8s_object_name="my-pod" | k8s_event_reason="FailedScheduling"
```

### What's Causing Pod Restarts?

```logql
{log_source="events"} | json | k8s_object_name=~"my-deployment-.*" | k8s_event_reason=~"BackOff|Unhealthy|OOMKilled"
```

### Recent Node Issues

```logql
{log_source="events"} | json | k8s_object_kind="Node" | line_format "{{.k8s_node_name}}: {{.body}}"
```

### All Events for an Application

```logql
{log_source="events"} | json | k8s_namespace_name="grafana" | line_format "{{.k8s_event_reason}}: {{.body}}"
```

## Combining with Pod Logs

To investigate an issue, query both events and pod logs:

```logql
# Events for the app
{log_source="events"} | json | k8s_namespace_name="my-app"

# Pod logs for the app
{log_source="pods", k8s_namespace_name="my-app"}
```

## Retention

Events are retained for 28 days in Loki (same as pod logs). Kubernetes only retains events in etcd for approximately 1 hour, so Loki provides long-term event history.

## Related

- [Logging Architecture](../reference/logging-architecture.md)
- [Query Logs](query-logs.md)
