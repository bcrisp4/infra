# Linkerd Installation Guide with cert-manager (Helm)

This guide covers installing Linkerd with automatic certificate management via cert-manager. No manual certificate generation required.

## Prerequisites

- `kubectl` configured for your cluster
- `helm` v3+
- cert-manager already installed
- trust-manager (we'll install if needed)

### Verify DOKS Cilium Compatibility

```bash
kubectl get configmaps -n kube-system cilium-config -oyaml | grep -E "bpf-lb-sock|cni-exclusive"
```

Expected:
```
bpf-lb-sock-hostns-only: "true"
cni-exclusive: "false"
```

---

## Step 1: Install trust-manager (if not already installed)

trust-manager distributes the trust anchor to the Linkerd namespace.

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install trust-manager jetstack/trust-manager \
  --namespace cert-manager \
  --set app.trust.namespace=cert-manager \
  --wait
```

---

## Step 2: Create the Linkerd Namespace

```bash
kubectl create namespace linkerd
```

---

## Step 3: Create cert-manager Resources for Linkerd

Apply all of these resources:

```yaml
# 01-trust-anchor-issuer.yaml
# Self-signed issuer for creating the trust anchor
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: linkerd-trust-anchor-selfsigned
  namespace: cert-manager
spec:
  selfSigned: {}
---
# 02-trust-anchor-certificate.yaml
# The trust anchor (root CA) - stored in cert-manager namespace
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: linkerd-trust-anchor
  namespace: cert-manager
spec:
  isCA: true
  commonName: root.linkerd.cluster.local
  secretName: linkerd-trust-anchor
  duration: 87600h    # 10 years
  renewBefore: 8760h  # 1 year before expiry
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  issuerRef:
    name: linkerd-trust-anchor-selfsigned
    kind: Issuer
    group: cert-manager.io
  usages:
    - cert sign
    - crl sign
    - server auth
    - client auth
---
# 03-linkerd-identity-issuer.yaml  
# ClusterIssuer that uses the trust anchor to sign identity certs
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: linkerd-identity-issuer
spec:
  ca:
    secretName: linkerd-trust-anchor
---
# 04-identity-issuer-certificate.yaml
# The identity issuer certificate - stored in linkerd namespace
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: linkerd-identity-issuer
  namespace: linkerd
spec:
  isCA: true
  commonName: identity.linkerd.cluster.local
  secretName: linkerd-identity-issuer
  duration: 48h
  renewBefore: 25h
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  issuerRef:
    name: linkerd-identity-issuer
    kind: ClusterIssuer
    group: cert-manager.io
  dnsNames:
    - identity.linkerd.cluster.local
  usages:
    - cert sign
    - crl sign
    - server auth
    - client auth
---
# 05-trust-bundle.yaml
# trust-manager Bundle to distribute trust anchor to linkerd namespace
apiVersion: trust.cert-manager.io/v1alpha1
kind: Bundle
metadata:
  name: linkerd-identity-trust-roots
spec:
  sources:
    - secret:
        name: linkerd-trust-anchor
        key: ca.crt
  target:
    configMap:
      key: ca-bundle.crt
    namespaceSelector:
      matchLabels:
        linkerd.io/is-control-plane: "true"
```

Apply:
```bash
kubectl apply -f 01-trust-anchor-issuer.yaml
kubectl apply -f 02-trust-anchor-certificate.yaml

# Wait for trust anchor to be ready
kubectl wait --for=condition=Ready certificate/linkerd-trust-anchor -n cert-manager --timeout=60s

kubectl apply -f 03-linkerd-identity-issuer.yaml
kubectl apply -f 04-identity-issuer-certificate.yaml

# Wait for identity issuer to be ready  
kubectl wait --for=condition=Ready certificate/linkerd-identity-issuer -n linkerd --timeout=60s

kubectl apply -f 05-trust-bundle.yaml
```

### Verify certificates are created

```bash
# Check certificates
kubectl get certificates -n cert-manager
kubectl get certificates -n linkerd

# Check secrets exist
kubectl get secret linkerd-trust-anchor -n cert-manager
kubectl get secret linkerd-identity-issuer -n linkerd
```

---

## Step 4: Add Linkerd Helm Repository

```bash
helm repo add linkerd https://helm.linkerd.io/stable
helm repo update
```

---

## Step 5: Install Linkerd CRDs

```bash
helm install linkerd-crds linkerd/linkerd-crds \
  -n linkerd
```

---

## Step 6: Install Linkerd Control Plane

```bash
helm install linkerd-control-plane linkerd/linkerd-control-plane \
  -n linkerd \
  --set identity.externalCA=true \
  --set identity.issuer.scheme=kubernetes.io/tls
```

Key flags:
- `identity.externalCA=true` - tells Linkerd to use externally-managed certificates
- `identity.issuer.scheme=kubernetes.io/tls` - use the standard TLS secret format that cert-manager creates

### High Availability (Production)

```bash
helm install linkerd-control-plane linkerd/linkerd-control-plane \
  -n linkerd \
  --set identity.externalCA=true \
  --set identity.issuer.scheme=kubernetes.io/tls \
  --set controllerReplicas=3 \
  --set enablePodAntiAffinity=true
```

---

## Step 7: Verify Installation

```bash
# Install linkerd CLI (optional but useful)
curl -sL https://run.linkerd.io/install | sh
export PATH=$HOME/.linkerd2/bin:$PATH

# Check health
linkerd check

# Check pods
kubectl get pods -n linkerd
```

---

## Step 8: Install Viz Extension (Optional)

```bash
helm install linkerd-viz linkerd/linkerd-viz \
  -n linkerd-viz \
  --create-namespace
```

---

## Step 9: Inject Workloads

### Namespace-level injection

```bash
kubectl annotate namespace <your-namespace> linkerd.io/inject=enabled
kubectl rollout restart deployment -n <your-namespace>
```

### Verify mTLS

```bash
linkerd viz edges deployment -n <your-namespace>
```

---

## How Certificate Rotation Works

With this setup:

1. **Identity issuer** (48h validity, renews at 25h): cert-manager automatically rotates this. Linkerd's identity controller watches the secret and picks up new certs.

2. **Trust anchor** (10 year validity, renews at 1 year before expiry): cert-manager handles rotation. trust-manager automatically updates the trust bundle in the linkerd namespace.

3. **Workload certificates** (24h validity): Linkerd handles these automatically - no action needed.

You don't need to do anything manual for rotation.

---

## Authorization Policies

Once mTLS is working, add authorization:

### Example: Restrict access to a service

```yaml
# Server - defines what to protect
apiVersion: policy.linkerd.io/v1beta1
kind: Server
metadata:
  name: my-app-http
  namespace: my-namespace
spec:
  podSelector:
    matchLabels:
      app: my-app
  port: 8080
  proxyProtocol: HTTP/1
---
# MeshTLSAuthentication - defines who can access
apiVersion: policy.linkerd.io/v1alpha1
kind: MeshTLSAuthentication
metadata:
  name: my-app-clients
  namespace: my-namespace
spec:
  identities:
    # ServiceAccount-based identity
    - "allowed-client.my-namespace.serviceaccount.identity.linkerd.cluster.local"
---
# AuthorizationPolicy - binds them together
apiVersion: policy.linkerd.io/v1alpha1
kind: AuthorizationPolicy
metadata:
  name: my-app-authz
  namespace: my-namespace
spec:
  targetRef:
    group: policy.linkerd.io
    kind: Server
    name: my-app-http
  requiredAuthenticationRefs:
    - name: my-app-clients
      kind: MeshTLSAuthentication
      group: policy.linkerd.io
---
# Allow kubelet probes (required!)
apiVersion: policy.linkerd.io/v1alpha1
kind: NetworkAuthentication
metadata:
  name: kubelet
  namespace: my-namespace
spec:
  networks:
    - cidr: 0.0.0.0/0
---
apiVersion: policy.linkerd.io/v1alpha1
kind: AuthorizationPolicy
metadata:
  name: allow-probes
  namespace: my-namespace
spec:
  targetRef:
    group: policy.linkerd.io
    kind: Server
    name: my-app-http
  requiredAuthenticationRefs:
    - name: kubelet
      kind: NetworkAuthentication
      group: policy.linkerd.io
```

---

## Troubleshooting

### cert-manager certificates not ready

```bash
kubectl describe certificate linkerd-trust-anchor -n cert-manager
kubectl describe certificate linkerd-identity-issuer -n linkerd
```

### Linkerd identity controller can't find certs

```bash
kubectl logs -n linkerd deploy/linkerd-identity
kubectl get secret linkerd-identity-issuer -n linkerd -o yaml
```

### trust-manager not creating ConfigMap

```bash
kubectl describe bundle linkerd-identity-trust-roots
kubectl get configmap linkerd-identity-trust-roots -n linkerd
```

The linkerd namespace needs the label `linkerd.io/is-control-plane: "true"` for trust-manager to sync. The Linkerd Helm chart adds this automatically.

### Pods not getting injected

```bash
kubectl get namespace <ns> -o yaml | grep linkerd
# Should show: linkerd.io/inject: enabled
```

---

## Quick Test

```bash
kubectl create namespace linkerd-test
kubectl annotate namespace linkerd-test linkerd.io/inject=enabled

kubectl -n linkerd-test run server --image=nginx --port=80
kubectl -n linkerd-test expose pod server --port=80
kubectl -n linkerd-test run client --image=curlimages/curl --command -- sleep infinity

kubectl wait --for=condition=Ready pod/server pod/client -n linkerd-test --timeout=120s

# Should show 2/2 containers
kubectl get pods -n linkerd-test

# Test connectivity
kubectl -n linkerd-test exec client -- curl -s http://server

# Verify mTLS
linkerd viz edges pod -n linkerd-test
```

---

## References

- Linkerd + cert-manager: https://linkerd.io/2-edge/tasks/automatically-rotating-control-plane-tls-credentials/
- cert-manager concepts: https://docs.buoyant.io/buoyant-enterprise-linkerd/latest/guides/cert-manager-concepts/
- Authorization Policies: https://linkerd.io/2-edge/features/server-policy/
