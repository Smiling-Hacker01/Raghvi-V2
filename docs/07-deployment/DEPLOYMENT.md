# Deployment Guide

## Overview

This guide covers deploying the Raghvi backend to production/staging environments. The Android app is distributed via internal testing (Google Play Internal Testing or direct APK).

---

## Prerequisites

### Infrastructure

- **Container Orchestration**: Kubernetes (recommended) or Docker Swarm / single-server Docker Compose
- **Database**: Managed PostgreSQL (AWS RDS, Google Cloud SQL, Azure Database, Neon, Supabase)
- **Object Storage**: AWS S3 / GCS / Azure Blob (for voice samples)
- **Secrets Management**: AWS Secrets Manager / GCP Secret Manager / HashiCorp Vault / Doppler
- **CDN/Load Balancer**: Cloudflare / AWS ALB / GCP Load Balancer / Nginx
- **Monitoring**: Prometheus + Grafana / Datadog / New Relic / Sentry
- **CI/CD**: GitHub Actions (existing) → deploy to staging/production

### External Services

| Service | Purpose | Required For |
|---------|---------|--------------|
| PostgreSQL | Primary database | All features |
| Redis | Caching, rate limiting, background jobs | Production scaling |
| Stripe | Payments, subscriptions | Voice features, monetization |
| AI Providers | LLM inference | Chat (at least 1) |
| Voice Providers | TTS, cloning | Voice features |
| AWS S3 | Voice sample storage | Voice cloning |
| Email (SendGrid, SES) | Transactional emails | Account verification, receipts |

---

## Environment Configuration

### Required Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/raghvi
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10

# Redis (production)
REDIS_URL=redis://:password@host:6379/0

# JWT
JWT_SECRET_KEY=<32+ char random string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# AI Providers (at least one)
AI_PROVIDER=gemini
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
HUGGINGFACE_API_KEY=hf_...
GITHUB_TOKEN=ghp_...

# Voice Providers
ELEVENLABS_API_KEY=...
CARTESIA_API_KEY=...
DEEPGRAM_API_KEY=...
NVIDIA_API_KEY=...
VOICE_PROVIDER_PRIORITY=elevenlabs,cartesia,deepgram,coqui_xtts

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_FREE=price_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_PREMIUM=price_...

# AWS/S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=raghvi-voice-prod
S3_REGION=us-east-1
S3_VOICE_PREFIX=voices/

# CORS
CORS_ALLOWED_ORIGINS=https://app.raghvi.example.com,https://staging.raghvi.example.com

# App
ENVIRONMENT=production
LOG_LEVEL=info
SENTRY_DSN=https://...@sentry.io/...
```

### Secrets Management

**Never commit secrets to git.** Use:

- **Local**: `.env` files (gitignored)
- **CI/CD**: GitHub Actions Secrets / Repository Environments
- **Production**: AWS Secrets Manager / GCP Secret Manager / Vault
- **Kubernetes**: Sealed Secrets / External Secrets Operator

---

## Docker Image

### Build

```bash
# Multi-platform build for production
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/your-org/raghvi-backend:v1.2.3 \
  --push \
  ./backend
```

### Dockerfile (backend/Dockerfile)

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --locked --no-dev

# Copy application
COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## Database Migrations

### Run Migrations

```bash
# Option 1: As init container (Kubernetes)
# Option 2: Pre-deploy step in CI/CD
# Option 3: Manual (staging only)

uv run alembic upgrade head
```

### Migration Strategy

- **Backward compatible**: Add columns with defaults, never drop columns in same release
- **Test in staging**: Run migrations against staging DB copy first
- **Rollback plan**: Keep `alembic downgrade -1` tested

---

## Kubernetes Deployment (Recommended)

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: raghvi
  labels:
    name: raghvi
```

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: raghvi-config
  namespace: raghvi
data:
  AI_PROVIDER: "gemini"
  VOICE_PROVIDER_PRIORITY: "elevenlabs,cartesia,deepgram,coqui_xtts"
  LOG_LEVEL: "info"
  ENVIRONMENT: "production"
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: raghvi-secrets
  namespace: raghvi
type: Opaque
stringData:
  DATABASE_URL: "postgresql+asyncpg://..."
  JWT_SECRET_KEY: "..."
  OPENAI_API_KEY: "..."
  GEMINI_API_KEY: "..."
  STRIPE_API_KEY: "..."
  STRIPE_WEBHOOK_SECRET: "..."
  AWS_ACCESS_KEY_ID: "..."
  AWS_SECRET_ACCESS_KEY: "..."
  SENTRY_DSN: "..."
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: raghvi-backend
  namespace: raghvi
spec:
  replicas: 3
  selector:
    matchLabels:
      app: raghvi-backend
  template:
    metadata:
      labels:
        app: raghvi-backend
    spec:
      containers:
      - name: backend
        image: ghcr.io/your-org/raghvi-backend:v1.2.3
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: raghvi-config
        - secretRef:
            name: raghvi-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      # Init container for migrations
      initContainers:
      - name: migrate
        image: ghcr.io/your-org/raghvi-backend:v1.2.3
        command: ["uv", "run", "alembic", "upgrade", "head"]
        envFrom:
        - configMapRef:
            name: raghvi-config
        - secretRef:
            name: raghvi-secrets
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: raghvi-backend
  namespace: raghvi
spec:
  selector:
    app: raghvi-backend
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: raghvi-backend
  namespace: raghvi
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "20m"
spec:
  tls:
  - hosts:
    - api.raghvi.example.com
    secretName: raghvi-tls
  rules:
  - host: api.raghvi.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: raghvi-backend
            port:
              number: 80
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: raghvi-backend-hpa
  namespace: raghvi
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: raghvi-backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Docker Compose (Single Server / Staging)

```yaml
# compose.prod.yml
version: '3.8'

services:
  backend:
    image: ghcr.io/your-org/raghvi-backend:v1.2.3
    restart: unless-stopped
    env_file:
      - .env.prod
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
    depends_on:
      - backend

volumes:
  redis_data:
```

---

## Database Setup (Managed PostgreSQL)

### Recommended Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Version | PostgreSQL 16+ | |
| Instance Class | db.t3.medium (start) | Scale based on load |
| Storage | 100 GB GP3, auto-scale | |
| Multi-AZ | Yes (production) | High availability |
| Backup Retention | 30 days | Point-in-time recovery |
| Performance Insights | Enabled | Query analysis |
| Parameter Group | Custom | See below |

### Custom Parameters

```ini
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
random_page_cost = 1.1
effective_io_concurrency = 200
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
```

### Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For future full-text search
-- CREATE EXTENSION IF NOT EXISTS vector;  -- For pgvector (future)
```

---

## Stripe Configuration

### Products & Prices

Create in Stripe Dashboard:

| Product | Price ID | Amount | Interval |
|---------|----------|--------|----------|
| Free | price_free | $0 | month |
| Pro | price_pro | $9.99 | month |
| Premium | price_premium | $24.99 | month |

### Webhook Endpoint

```
URL: https://api.raghvi.example.com/webhooks/stripe
Events:
  - checkout.session.completed
  - customer.subscription.created
  - customer.subscription.updated
  - customer.subscription.deleted
  - invoice.payment_failed
  - invoice.payment_succeeded
```

### Test Mode

Use Stripe test keys for staging:
- `sk_test_...` / `pk_test_...`
- Webhook: `https://staging-api.raghvi.example.com/webhooks/stripe`

---

## CI/CD Pipeline

### GitHub Actions (`.github/workflows/deploy.yml`)

```yaml
name: Deploy to Staging

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    uses: ./.github/workflows/backend-ci.yml

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/raghvi-backend \
            backend=ghcr.io/${{ github.repository }}/backend:${{ github.sha}} \
            -n raghvi-staging
          kubectl rollout status deployment/raghvi-backend -n raghvi-staging

  deploy-production:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/raghvi-backend \
            backend=ghcr.io/${{ github.repository }}/backend:${{ github.sha}} \
            -n raghvi
          kubectl rollout status deployment/raghvi-backend -n raghvi
```

### Required GitHub Environments

- `staging` — Auto-deploy on main branch push
- `production` — Manual approval required

### Required Secrets (GitHub)

| Secret | Description |
|--------|-------------|
| `KUBECONFIG_STAGING` | Base64 kubeconfig for staging cluster |
| `KUBECONFIG_PRODUCTION` | Base64 kubeconfig for production cluster |
| `GHCR_TOKEN` | GitHub Container Registry token |
| `STRIPE_WEBHOOK_SECRET` | For local testing |

---

## Android App Distribution

### Build Release

```bash
cd android
./gradlew bundleRelease
# Output: app/build/outputs/bundle/release/app-release.aab
```

### Google Play Internal Testing

1. Upload `.aab` to Play Console → Internal Testing
2. Add testers via email list
3. Testers get invite link to install

### Direct APK (Development)

```bash
./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
```

### App Configuration

Update `android/app/src/main/java/com/raghvi/assistant/network/ApiClient.kt`:

```kotlin
// Production
private const val BASE_URL = "https://api.raghvi.example.com/"

// Staging
private const val BASE_URL = "https://staging-api.raghvi.example.com/"
```

---

## Post-Deployment Verification

### Health Checks

```bash
# Backend health
curl https://api.raghvi.example.com/health
curl https://api.raghvi.example.com/ready

# API smoke test
curl -X POST https://api.raghvi.example.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'

# Voice synthesis
curl -X POST https://api.raghvi.example.com/voices/synthesize \
  -H "Authorization: Bearer <token>" \
  -F "text=Hello world"
```

### Monitoring Dashboards

- **Latency**: p50, p95, p99 for `/chat/send`, `/chat/send-with-voice`
- **Error Rate**: 5xx by endpoint
- **AI Provider Failover Rate**: Chain attempts per request
- **Voice Synthesis Latency**: Per provider
- **Database**: Connections, query latency, replication lag
- **Stripe**: Webhook success rate, subscription events

---

## Rollback Procedure

```bash
# Kubernetes
kubectl rollout undo deployment/raghvi-backend -n raghvi

# Docker Compose
docker compose -f compose.prod.yml pull  # Previous tag
docker compose -f compose.prod.yml up -d

# Database (if migration caused issue)
uv run alembic downgrade -1
```

---

## Security Checklist

- [ ] All secrets in secret manager (not env vars in repo)
- [ ] TLS 1.2+ enforced (HSTS, secure headers)
- [ ] CORS restricted to known origins
- [ ] Rate limiting on auth endpoints
- [ ] Stripe webhook signature verification
- [ ] S3 bucket: private, no public access
- [ ] Database: SSL required, no public access
- [ ] Sentry/APM configured for error tracking
- [ ] Dependency scanning (Dependabot/Snyk)
- [ ] Container image scanning (Trivy/Snyk)