# Host Logs Collection

Collect host-level logs (kubelet, containerd, systemd services) in addition to pod logs.

## Current State

Only pod logs are collected via the `filelog` receiver reading `/var/log/pods/*/*/*.log`.

Host/systemd logs are not collected because the journald receiver requires the `journalctl` binary, which is not included in the `otel/opentelemetry-collector-contrib` container image.

## What Was Tried

### Journald Receiver

The original plan included a journald receiver to collect logs from systemd:

```yaml
receivers:
  journald:
    directory: /var/log/journal
    units:
      - kubelet
      - containerd
      - docker
    priority: info
```

With volume mounts:

```yaml
extraVolumes:
  - name: journal
    hostPath:
      path: /var/log/journal
  - name: machine-id
    hostPath:
      path: /etc/machine-id

extraVolumeMounts:
  - name: journal
    mountPath: /var/log/journal
    readOnly: true
  - name: machine-id
    mountPath: /etc/machine-id
    readOnly: true
```

### Why It Failed

The collector pod crashed with:

```
exec: "journalctl": executable file not found in $PATH
```

The journald receiver internally shells out to `journalctl` to read the journal. The `otel/opentelemetry-collector-contrib` image is built on a minimal base image (distroless or Alpine) that does not include systemd utilities.

## DOKS Node Reality (Verified)

Verified via `kubectl debug node` on DOKS worker nodes:

**Log locations:**
- `/var/log/syslog` - **DOES NOT EXIST** (eliminates filelog/syslog option)
- `/var/log/journal/` - **EXISTS** with persistent journals:
  - Multiple machine-ID directories (one per boot)
  - `system.journal` files at ~128MB each
  - Total ~789MB of journal data per node
- `/var/log/containers/` - Raw container logs
- `/var/log/pods/` - Kubernetes pod logs (already collected via otel-logs filelog)
- `/var/log/cloud-init.log` - Cloud-init logs

**Conclusion:** Only journald-based options are viable on DOKS.

## Solutions

### Option 1: Custom Collector Image (Recommended)

Build a custom OpenTelemetry Collector image that includes `journalctl`:

```dockerfile
FROM otel/opentelemetry-collector-contrib:0.120.0

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends systemd && \
    rm -rf /var/lib/apt/lists/*
USER 10001
```

**Pros:**
- Uses the native journald receiver
- Proper structured log parsing
- Filters by unit, priority, etc.

**Cons:**
- Requires maintaining a custom image
- Must rebuild when upstream collector updates

### Option 2: Filelog Receiver for Syslog

~~Read traditional syslog files instead of the journal.~~

**Status: NOT VIABLE on DOKS**

DOKS nodes do not write traditional syslog files (`/var/log/syslog`, `/var/log/messages`). Systemd writes only to the binary journal at `/var/log/journal/`.

### Option 3: journalctl Sidecar (Alternative)

Run a sidecar container that tails the journal and writes to a file the collector can read:

```yaml
# Sidecar in DaemonSet
- name: journal-tailer
  image: debian:bookworm-slim
  command:
    - sh
    - -c
    - |
      apt-get update && apt-get install -y systemd
      journalctl -f -u kubelet -u containerd --output=json > /var/log/journal-export/journal.log
  volumeMounts:
    - name: journal
      mountPath: /var/log/journal
      readOnly: true
    - name: machine-id
      mountPath: /etc/machine-id
      readOnly: true
    - name: journal-export
      mountPath: /var/log/journal-export
```

Then use filelog receiver to read `/var/log/journal-export/journal.log`.

**Pros:**
- Works with stock collector image
- JSON output is easy to parse

**Cons:**
- Additional container per node
- More resource usage
- More complex configuration

## Recommendation

For DOKS clusters, **Option 1 (Custom Image)** is the cleanest solution if host logs are required.

However, consider whether host logs are truly needed:

- **kubelet logs**: Most kubelet issues manifest as pod events, which are visible via `kubectl describe pod`
- **containerd logs**: Container runtime issues usually surface as pod failures
- **Node issues**: DigitalOcean handles node-level issues for managed Kubernetes

Pod logs cover 90%+ of debugging needs. Host logs are mainly useful for:
- Investigating node-level networking issues
- Debugging kubelet configuration problems
- Auditing node access (if SSH is enabled)

## Implementation Checklist

If proceeding with Option 1:

- [ ] Create Dockerfile for custom collector image
- [ ] Set up CI/CD to build and push image
- [ ] Update otel-logs values.yaml to use custom image
- [ ] Add journald receiver configuration
- [ ] Add volume mounts for journal and machine-id
- [ ] Add `resource/journal` processor for `log_source: journal` label
- [ ] Add `logs/journal` pipeline
- [ ] Test and verify host logs appear in Loki
- [ ] Update documentation

## Related

- [Logging Architecture](../reference/logging-architecture.md)
- [Query Logs](../how-to/query-logs.md)
