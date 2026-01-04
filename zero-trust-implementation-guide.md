# Zero-Trust Kubernetes Implementation Guide

## Architecture

Layered zero-trust using Cilium (L3/L4) + Istio ambient (identity/L7).

**Enforcement order**: Cilium (kernel eBPF) → ztunnel (L4 mTLS) → waypoint (L7)

**Key constraint**: Cilium does NOT support Kubernetes AdminNetworkPolicy/BaseAdminNetworkPolicy. Use CiliumClusterwideNetworkPolicy instead for cluster-wide rules.

## Documentation References

- Cilium Network Policies: https://docs.cilium.io/en/stable/security/policy/
- CiliumClusterwideNetworkPolicy: https://docs.cilium.io/en/stable/security/policy/language/#ciliumclusterwidenetworkpolicy
- Cilium FQDN Policies: https://docs.cilium.io/en/stable/security/policy/language/#dns-based
- Istio Ambient Overview: https://istio.io/latest/docs/ambient/overview/
- Istio L4 Policy (ztunnel): https://istio.io/latest/docs/ambient/usage/l4-policy/
- Istio L7 Features (waypoint): https://istio.io/latest/docs/ambient/usage/l7-features/
- Istio AuthorizationPolicy: https://istio.io/latest/docs/reference/config/security/authorization-policy/
- Istio PeerAuthentication: https://istio.io/latest/docs/reference/config/security/peer_authentication/
- Istio Ambient + NetworkPolicy: https://istio.io/latest/docs/ambient/usage/networkpolicy/
- Istio Waypoint Configuration: https://istio.io/latest/docs/ambient/usage/waypoint/

## Policy Layers to Implement

### Layer 1: Cilium Cluster-Wide Policies

Create CiliumClusterwideNetworkPolicy resources for:

1. **Allow DNS** - All workloads need DNS to kube-dns (UDP/TCP 53). Include DNS proxy rules for FQDN policy support.

2. **Allow Istio Ambient** - HBONE tunnel traffic on port 15008, plus health probe SNAT address 169.254.7.127.

3. **Block Metadata Service** - Deny egress to 169.254.169.254/32 (cloud metadata endpoint).

4. **Baseline Default-Deny** - Empty ingress/egress for all workload namespaces. Exclude system namespaces: kube-system, kube-public, kube-node-lease, cilium-system, istio-system.

**Deployment order matters**: Apply allow rules before default-deny to avoid breaking the cluster.

### Layer 2: Namespace Default-Deny

Apply standard Kubernetes NetworkPolicy with empty ingress/egress to each workload namespace. This provides defense-in-depth alongside Cilium policies.

### Layer 3: Istio Mesh-Wide mTLS

Apply PeerAuthentication in istio-system namespace with mode: STRICT to enforce mTLS for all mesh traffic.

### Layer 4: Istio L4 Authorization (ztunnel)

Use AuthorizationPolicy with `selector` for L4 rules enforced by ztunnel. Only L4 attributes work without waypoints:
- `principals` (service account identity)
- `namespaces`
- `ipBlocks`
- `ports`

### Layer 5: Istio L7 Authorization (waypoint)

For HTTP method/path restrictions, JWT validation, or header-based rules, deploy a waypoint proxy. Waypoints are standard Kubernetes Gateway resources - no istioctl required.

**Waypoint Gateway resource:**
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: waypoint
  namespace: <namespace>
  labels:
    istio.io/waypoint-for: service  # "service", "workload", "all", or "none"
spec:
  gatewayClassName: istio-waypoint
  listeners:
    - name: mesh
      port: 15008
      protocol: HBONE
```

**Enroll namespace (label the Namespace):**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: <namespace>
  labels:
    istio.io/dataplane-mode: ambient
    istio.io/use-waypoint: waypoint  # Gateway name
```

**Or enroll specific services only:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  labels:
    istio.io/use-waypoint: waypoint
```

Then use AuthorizationPolicy with `targetRefs` pointing to the Service or Gateway.

### Layer 6: FQDN Egress Control

Use CiliumNetworkPolicy per-namespace with toFQDNs rules. Requires corresponding DNS rules to allow resolution of the FQDNs.

## Critical Implementation Notes

- Cilium sees encrypted HBONE traffic on port 15008, not actual application ports. L4 filtering by app port must happen at Istio layer.

- L7 AuthorizationPolicy using `selector` (targeting ztunnel) with HTTP attributes fails closed as deny-all. Must use `targetRefs` with waypoint deployed.

- FQDN policies only work after DNS proxy intercepts the query. Ensure DNS allow rules include the `rules.dns` section.

- Istio ambient SNATs kubelet health probes to 169.254.7.127. Policies must allow this or probes fail.

- With waypoints deployed, destination ztunnel sees waypoint's identity, not original source. Plan authorization rules accordingly.

## Verification

```bash
# Cilium policy status (run inside cilium-agent pod)
kubectl exec -n kube-system ds/cilium -- cilium policy get
kubectl exec -n kube-system ds/cilium -- cilium endpoint list

# Istio authorization check
istioctl x authz check <pod>.<namespace>

# mTLS verification
istioctl proxy-config secret <pod>.<namespace>

# Traffic observation (requires Hubble)
hubble observe --namespace <ns>
```

## Rollout Strategy

1. Audit existing traffic with `hubble observe` before applying default-deny
2. Apply allow rules first, then default-deny
3. Start with a single non-critical namespace
4. Add service-specific policies incrementally
5. Deploy waypoints only for services requiring L7 authorization
