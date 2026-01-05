# ArgoCD Troubleshooting

Common issues with ArgoCD application deployment and synchronization.

## Application not syncing after push

**Symptom:** Pushed changes but application shows "OutOfSync" or doesn't update.

1. Check webhook is configured and delivering:
   - GitHub: Repository Settings > Webhooks > Recent Deliveries
   - Look for 200 response codes

2. If webhook not configured, ArgoCD polls every 3 minutes
   - Wait for poll interval or manually refresh

3. Manual refresh:
   ```bash
   argocd app get <app-name> --refresh
   # Or in UI: click "Refresh" button
   ```

## Webhook returns 400 Bad Request

**Symptom:** GitHub webhook shows 400 response in Recent Deliveries.

**Causes:**

1. Wrong content type - must be `application/json`:
   - Edit webhook > Content type > Select "application/json"

2. Secret mismatch:
   - Verify `webhook.github.secret` in `argocd-secret` matches GitHub webhook secret

3. Check ArgoCD server logs:
   ```bash
   kubectl logs -n argocd deployment/argocd-server --tail=100 | grep -i webhook
   ```

## Webhook connection timeout

**Symptom:** GitHub shows "timed out" or "failed to connect" for webhook delivery.

For Tailscale Funnel setup:

1. Verify Funnel ingress has address:
   ```bash
   kubectl get ingress -n argocd argocd-webhook-funnel
   ```

2. Test Funnel URL from outside tailnet:
   ```bash
   curl -I https://argocd-webhook-<cluster>.<tailnet>.ts.net/api/webhook
   ```

3. Check Tailscale ACLs have `funnel` attribute on `tag:k8s`

See [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md) for setup guide.

## Application stuck in "Progressing"

**Symptom:** Application shows "Progressing" indefinitely.

1. Check for failing pods:
   ```bash
   kubectl get pods -n <app-namespace> --field-selector=status.phase!=Running
   ```

2. Check events:
   ```bash
   kubectl get events -n <app-namespace> --sort-by='.lastTimestamp'
   ```

3. Check deployment rollout status:
   ```bash
   kubectl rollout status deployment/<deployment> -n <app-namespace>
   ```

## Sync fails with "ComparisonError"

**Symptom:** Application shows "ComparisonError" or "Unknown" status.

1. Check ArgoCD can access the Git repository:
   ```bash
   argocd repo list
   ```

2. Verify repository credentials are valid

3. Check for YAML syntax errors in manifests:
   ```bash
   kubectl apply --dry-run=client -f <manifest.yaml>
   ```

## Namespace not created

**Symptom:** Resources fail to create because namespace doesn't exist.

**Fix:** Enable `CreateNamespace` sync option in ApplicationSet or Application:
```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true
```

## Helm chart dependency issues

**Symptom:** Application fails with "chart not found" or dependency errors.

1. Update Helm dependencies locally:
   ```bash
   cd kubernetes/apps/<app>
   helm dependency update
   ```

2. Commit the updated `Chart.lock` file

3. ArgoCD should now be able to resolve dependencies

## Resource diff shows unexpected changes

**Symptom:** ArgoCD shows diff for fields you didn't change.

**Common causes:**

1. Defaulted values - Kubernetes adds defaults that ArgoCD sees as drift
   - Add to `.spec.ignoreDifferences` in Application

2. Managed fields - controllers modify resources
   - Use server-side diff: `syncOptions: [ServerSideApply=true]`

3. Helm hook resources - temporary resources cause noise
   - Check hook annotations

## ApplicationSet not generating Applications

**Symptom:** ApplicationSet exists but no Applications are created.

1. Check ApplicationSet controller logs:
   ```bash
   kubectl logs -n argocd deployment/argocd-applicationset-controller --tail=100
   ```

2. Verify Git files generator path matches actual file structure

3. Check config.yaml files exist in expected locations:
   ```bash
   ls kubernetes/clusters/<cluster>/apps/*/config.yaml
   ```

## Related

- [ArgoCD Webhooks via Tailscale Funnel](../how-to/argocd-webhook-tailscale-funnel.md)
- [ArgoCD Manifests Reference](../reference/argocd-manifests.md)
