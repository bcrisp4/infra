# GitHub Webhooks to Private ArgoCD via Tailscale Funnel

This guide explains how to receive GitHub webhooks in an ArgoCD instance that isn't exposed to the public internet, using Tailscale Funnel and the Tailscale Kubernetes Operator.

## The Problem

ArgoCD polls Git repositories every 3 minutes by default. Webhooks eliminate this delay by having GitHub notify ArgoCD immediately when changes are pushed. However, webhooks require a publicly accessible endpoint, which is a problem when ArgoCD is only accessible within a private Tailscale tailnet.

## The Solution

Tailscale Funnel exposes a specific path from your private cluster to the public internet, tunneled securely through Tailscale's infrastructure. Using the Tailscale Kubernetes Operator, we can create an Ingress that exposes only the `/api/webhook` endpoint publicly while keeping the rest of ArgoCD private.

**Note:** This ingress uses a **standalone proxy**, not the shared ProxyGroup. Funnel ingresses require path-based routing (`rules` with `paths`), which ProxyGroup doesn't support. Additionally, public-facing endpoints benefit from isolation. See [Migrate Ingress to ProxyGroup](tailscale-proxygroup-ingress.md#when-not-to-use-proxygroup) for details.

## Prerequisites

- Kubernetes cluster with ArgoCD installed
- Tailscale Kubernetes Operator installed and configured
- MagicDNS and HTTPS enabled for your tailnet
- Admin access to your Tailscale ACLs

## Step 1: Update Tailscale ACLs

Add the `funnel` attribute to the tag used by your Kubernetes operator proxies. By default, this is `tag:k8s`.

In your Tailscale admin console, go to **Access Controls** and add or update the `nodeAttrs` section:

```json
{
  "nodeAttrs": [
    {
      "target": ["tag:k8s"],
      "attr": ["funnel"]
    }
  ]
}
```

> **Note:** Even if your policy has the `funnel` attribute assigned to `autogroup:member`, you still need to add it explicitly to the tag used by proxies because `autogroup:member` does not include tagged devices.

## Step 2: Configure ArgoCD Webhook Secret

Create or update the ArgoCD secret to include your GitHub webhook secret. Generate a strong random secret first:

```bash
openssl rand -hex 32
```

Then add it to your ArgoCD secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-secret
  namespace: argocd
  labels:
    app.kubernetes.io/part-of: argocd
type: Opaque
stringData:
  # Add this line to your existing argocd-secret
  webhook.github.secret: "your-generated-secret-here"
```

If you're using the ArgoCD Helm chart, you can set this via values:

```yaml
configs:
  secret:
    extra:
      webhook.github.secret: "your-generated-secret-here"
```

## Step 3: Create the Funnel Ingress

Create an Ingress resource that exposes only the webhook path via Tailscale Funnel:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-webhook-funnel
  namespace: argocd
  annotations:
    tailscale.com/funnel: "true"
spec:
  ingressClassName: tailscale
  tls:
    - hosts:
        - argocd-webhook
  rules:
    - http:
        paths:
          - path: /api/webhook
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 80
```

Apply it:

```bash
kubectl apply -f argocd-webhook-ingress.yaml
```

### Notes on the Ingress configuration

- **`tailscale.com/funnel: "true"`** - This annotation is what makes the Ingress publicly accessible via Funnel rather than just within your tailnet.
- **`tls.hosts[0]`** - This becomes the hostname: `argocd-webhook.<your-tailnet>.ts.net`
- **`pathType: Prefix`** - This is the only path type the Tailscale operator supports. Requests to `/api/webhook` and any subpaths will match.
- **`port: 80`** - Use 80 if argocd-server handles TLS termination externally, or 443 if it terminates TLS itself.

## Step 4: Verify the Ingress

Wait for the Ingress to be assigned an address:

```bash
kubectl get ingress -n argocd argocd-webhook-funnel -w
```

You should see output like:

```
NAME                    CLASS       HOSTS   ADDRESS                              PORTS     AGE
argocd-webhook-funnel   tailscale   *       argocd-webhook.tailnet-name.ts.net   80, 443   2m
```

Verify the Funnel is working:

```bash
curl -I https://argocd-webhook.<your-tailnet>.ts.net/api/webhook
```

You should get a response (likely a 400 or 405 since we're not sending a proper webhook payload, but not a connection error).

## Step 5: Configure GitHub Webhook

1. Go to your repository (or organization) **Settings > Webhooks > Add webhook**

2. Configure the webhook:
   - **Payload URL:** `https://argocd-webhook.<your-tailnet>.ts.net/api/webhook`
   - **Content type:** `application/json` (required - ArgoCD doesn't support form-urlencoded)
   - **Secret:** The same secret you configured in Step 2
   - **SSL verification:** Enable
   - **Events:** Select "Just the push event" (or customize as needed)

3. Click **Add webhook**

4. GitHub will send a ping event. Check the webhook's **Recent Deliveries** to confirm it was received successfully (green checkmark, 200 response).

## Step 6: Test the Webhook

Make a commit to your repository and push it. Check the ArgoCD logs to verify the webhook was received:

```bash
kubectl logs -n argocd deployment/argocd-server | grep -i webhook
```

You should see something like:

```
level=info msg="Received push event repo: https://github.com/yourorg/yourrepo, revision: main, touchedHead: true"
```

## Troubleshooting

### Webhook returns 400 Bad Request

- Verify the Content-Type is set to `application/json` in GitHub
- Check the webhook secret matches between GitHub and `argocd-secret`

### Ingress not getting an address

- Check the Tailscale operator logs: `kubectl logs -n tailscale deployment/operator`
- Verify the `funnel` attribute is set correctly in your ACLs
- Ensure the operator's OAuth client has the necessary scopes

### ArgoCD not refreshing after webhook

- Verify the repository URL in the webhook payload matches what ArgoCD has configured
- Check that the branch/revision matches your Application's `targetRevision`
- Look for errors in the argocd-server logs

### Connection refused or timeout from GitHub

- Verify Funnel is enabled: `tailscale status` on a node should show Funnel capability
- Test the URL from outside your tailnet (e.g., from your phone with WiFi off)
- Check if there are any firewall rules blocking outbound connections from GitHub's IP ranges

## Security Considerations

1. **Webhook Secret:** Always configure a webhook secret. Without it, anyone who discovers your Funnel URL could trigger refreshes in ArgoCD (potential for DoS).

2. **Limited Exposure:** This setup only exposes `/api/webhook`. The ArgoCD UI, API, and other endpoints remain accessible only within your tailnet.

3. **Payload Size Limits:** Consider setting `webhook.maxPayloadSizeMB` in `argocd-cm` ConfigMap to limit payload sizes and prevent abuse:

   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: argocd-cm
     namespace: argocd
   data:
     webhook.maxPayloadSizeMB: "10"
   ```

4. **Audit Logging:** Funnel traffic appears in your Tailscale logs, giving you visibility into webhook requests.

## Alternative: ApplicationSet Webhooks

If you're using ApplicationSets with the Git generator, the same `/api/webhook` endpoint handles those webhooks too. No additional configuration is needed beyond what's described above.

## Related

- [ArgoCD Troubleshooting](../troubleshooting/argocd.md)
- [Tailscale Operator Reference](../reference/tailscale-operator.md)

## References

- [ArgoCD Webhook Configuration](https://argo-cd.readthedocs.io/en/latest/operator-manual/webhook/)
- [Tailscale Kubernetes Operator - Cluster Ingress](https://tailscale.com/kb/1439/kubernetes-operator-cluster-ingress)
- [Tailscale Funnel](https://tailscale.com/kb/1223/funnel)
