# Deployment

## Docker Compose

```powershell
cp .env.example .env
docker compose up --build
```

Services:

- `postgres` - TimescaleDB
- `redis` - cache and stream coordination
- `kafka` - event bus
- `mlflow` - model tracking
- `backend` - FastAPI API
- `frontend` - static React app served by Nginx

## Kubernetes

```powershell
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/secret.example.yaml
kubectl apply -f infra/k8s/stateful-services.yaml
kubectl apply -f infra/k8s/backend.yaml
kubectl apply -f infra/k8s/frontend.yaml
kubectl apply -f infra/k8s/ingress.yaml
```

For production, replace the example secret, use managed PostgreSQL/TimescaleDB where available, configure Kafka with durable storage, and publish container images to a registry.

