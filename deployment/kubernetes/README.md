# Kubernetes Manifests

These manifests deploy the ClaimGuard AI backend and Streamlit
frontend into the `claimguard-ai` namespace.

Apply the namespace first:

```bash
kubectl apply -f deployment/kubernetes/namespace.yaml
```

Then create configuration and storage:

```bash
kubectl apply -f deployment/kubernetes/configmap.yaml
kubectl apply -f deployment/kubernetes/persistent-volume-claim.yaml
```

Create a real secret from your local environment instead of applying
the example placeholder directly:

```bash
kubectl create secret generic claimguard-secrets \
  --namespace claimguard-ai \
  --from-literal GEMINI_API_KEY="$GEMINI_API_KEY"
```

Deploy the services:

```bash
kubectl apply -f deployment/kubernetes/backend-deployment.yaml
kubectl apply -f deployment/kubernetes/backend-service.yaml
kubectl apply -f deployment/kubernetes/frontend-deployment.yaml
kubectl apply -f deployment/kubernetes/frontend-service.yaml
```

The manifests reference the local image tag `claimguard-ai:local`.
For a remote cluster, build and push the image to your registry and
replace the image value in both deployments.

The demo SQLite database, uploads, extracted text, field outputs, and
runtime model caches use the `claimguard-data` PVC. The trained fraud
model and policy vector store still need to be present in the image or
mounted by a cluster-specific mechanism before the backend can become
ready.
