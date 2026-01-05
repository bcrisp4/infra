# Query Kubernetes Events

Query Kubernetes events stored in Loki using LogQL.

## Prerequisites

- Access to Grafana (`grafana-do-nyc3-prod.marlin-tet.ts.net`)
- `loki-do-nyc3-prod` datasource configured

## Basic Queries

The k8s_events receiver stores all event metadata as labels, so no JSON parsing is needed. The log body contains just the event message.

### All Cluster Events

```logql
{log_source="events"}
```

### Events by Namespace

```logql
{log_source="events", k8s_namespace_name="argocd"}
```

### Events by Object Type

```logql
# Pod events
{log_source="events", k8s_object_kind="Pod"}

# Deployment events
{log_source="events", k8s_object_kind="Deployment"}

# Job events
{log_source="events", k8s_object_kind="Job"}

# Node events
{log_source="events", k8s_object_kind="Node"}
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
| `Completed` | Job completed |
| `FailedScheduling` | Pod could not be scheduled |
| `BackOff` | Container restarting with backoff |
| `Unhealthy` | Liveness/readiness probe failed |
| `ScalingReplicaSet` | ReplicaSet scaling |
| `OperationCompleted` | ArgoCD sync completed |

```logql
# Scheduling events
{log_source="events", k8s_event_reason="Scheduled"}

# Failed scheduling
{log_source="events", k8s_event_reason="FailedScheduling"}

# Container backoff (crash loops)
{log_source="events", k8s_event_reason="BackOff"}

# Probe failures
{log_source="events", k8s_event_reason="Unhealthy"}

# Job completions
{log_source="events", k8s_event_reason="Completed"}
```

### Warning Events

Events have a `severity_text` label set to `Normal` or `Warning`:

```logql
# All warnings
{log_source="events", severity_text="Warning"}

# Warnings in specific namespace
{log_source="events", k8s_namespace_name="mimir", severity_text="Warning"}
```

### Events for Specific Object

```logql
# Events for a specific pod
{log_source="events", k8s_object_name="grafana-0"}

# Events for objects matching a pattern
{log_source="events", k8s_object_name=~"mimir-.*"}
```

## Advanced Queries

### Failed Events (Multiple Reasons)

```logql
{log_source="events", k8s_event_reason=~"Failed.*|BackOff|Unhealthy|Error.*"}
```

### Recent Scaling Events

```logql
{log_source="events", k8s_event_reason=~"ScalingReplicaSet|SuccessfulRescale"}
```

### Image Pull Events

```logql
{log_source="events", k8s_event_reason=~"Pull.*|ErrImagePull|ImagePullBackOff"}
```

### Volume Events

```logql
{log_source="events", k8s_event_reason=~".*Volume.*|.*Mount.*|.*Attach.*"}
```

### ArgoCD Sync Events

```logql
{log_source="events", k8s_object_kind="Application", k8s_event_reason=~"OperationCompleted|ResourceUpdated"}
```

## Event Labels

All event metadata is available as labels (no `| json` needed):

| Label | Description |
|-------|-------------|
| `k8s_event_reason` | Event reason (Scheduled, Pulled, Failed, etc.) |
| `k8s_event_count` | Number of times event occurred |
| `k8s_event_name` | Event resource name |
| `k8s_event_uid` | Event UID |
| `k8s_event_start_time` | When the event first occurred |
| `k8s_namespace_name` | Namespace where event occurred |
| `k8s_object_kind` | Kind of involved object (Pod, Deployment, Job, etc.) |
| `k8s_object_name` | Name of involved object |
| `k8s_object_uid` | UID of involved object |
| `severity_text` | `Normal` or `Warning` |
| `cluster` | Cluster identifier |
| `log_source` | Always `events` |

## Troubleshooting Examples

### Why Won't My Pod Schedule?

```logql
{log_source="events", k8s_object_name="my-pod", k8s_event_reason="FailedScheduling"}
```

### What's Causing Pod Restarts?

```logql
{log_source="events", k8s_object_name=~"my-deployment-.*", k8s_event_reason=~"BackOff|Unhealthy|OOMKilled"}
```

### Recent Warning Events

```logql
{log_source="events", severity_text="Warning"} | line_format "{{.k8s_namespace_name}}/{{.k8s_object_name}}: {{__line__}}"
```

### All Events for an Application

```logql
{log_source="events", k8s_namespace_name="grafana"} | line_format "{{.k8s_event_reason}}: {{__line__}}"
```

## Combining with Pod Logs

To investigate an issue, query both events and pod logs:

```logql
# Events for the app
{log_source="events", k8s_namespace_name="my-app"}

# Pod logs for the app
{log_source="pods", k8s_namespace_name="my-app"}
```

## Retention

Events are retained for 28 days in Loki (same as pod logs). Kubernetes only retains events in etcd for approximately 1 hour, so Loki provides long-term event history.

## Related

- [Logging Architecture](../reference/logging-architecture.md)
- [Query Logs](query-logs.md)
