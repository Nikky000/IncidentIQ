# Deployment Guide

Production deployment guide for IncidentIQ.

## Deployment Options

1. **Docker Compose** (Recommended for small-medium scale)
2. **Kubernetes** (For large scale)
3. **Platform as a Service** (Railway, Render, Fly.io)

---

## Docker Compose Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- 10GB disk space

### Step 1: Prepare Environment

```bash
# Clone repository
git clone https://github.com/your-org/incidentiq.git
cd incidentiq

# Create .env file
cp .env.example .env
```

### Step 2: Configure Environment

Edit `.env`:

```bash
# Set secure database password
DB_PASSWORD=your_secure_password_here

# Set LLM provider
LLM_MODEL=anthropic/claude-3-5-sonnet
ANTHROPIC_API_KEY=your_api_key

# Set embedding provider
EMBEDDING_MODEL=openai/text-embedding-3-small
OPENAI_API_KEY=your_api_key

# Set Slack credentials
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
```

### Step 3: Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Step 4: Initialize Database

```bash
# Run database migrations
docker-compose exec api python -c "
import asyncio
from src.db.models import init_db
asyncio.run(init_db())
"
```

### Step 5: Verify Deployment

```bash
# Health check
curl http://localhost/health

# Should return:
# {"status":"healthy","version":"0.1.0"}
```

### Service URLs

- API: `http://localhost:80`
- Qdrant UI: `http://localhost:6333/dashboard`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

---

## Scaling

### Horizontal Scaling

```bash
# Scale API servers
docker-compose up -d --scale api=3

# Scale bot workers
docker-compose up -d --scale slack-bot=2
```

### Resource Limits

Edit `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

---

## SSL/TLS Configuration

### Option 1: Let's Encrypt with Certbot

```bash
# Generate certificates
docker run -it --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly \
  --standalone \
  -d your-domain.com

# Copy certs to config
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem config/ssl/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem config/ssl/
```

### Option 2: Custom Certificates

```bash
# Place certificates in config/ssl/
config/ssl/
├── certificate.crt
└── private.key
```

Update `config/nginx.conf`:

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/certificate.crt;
    ssl_certificate_key /etc/nginx/ssl/private.key;
    # ... rest of config
}
```

---

## Production Checklist

### Security

- [ ] Change default database password
- [ ] Use environment-specific API keys
- [ ] Enable SSL/TLS
- [ ] Configure CORS_ORIGINS
- [ ] Set up firewall rules
- [ ] Enable rate limiting

### Monitoring

- [ ] Set up health check monitoring
- [ ] Configure error tracking (Sentry)
- [ ] Set up log aggregation
- [ ] Configure alerts for service failures

### Performance

- [ ] Tune database connection pool
- [ ] Enable Redis persistence
- [ ] Configure Qdrant memory limits
- [ ] Set up CDN for static assets

### Backup

- [ ] Schedule PostgreSQL backups
- [ ] Backup Qdrant collection
- [ ] Backup Redis data (if persistence enabled)
- [ ] Test restore procedures

---

## Platform as a Service (PaaS)

### Railway Deployment

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Add services
railway add --service postgresql
railway add --service redis

# Set environment variables
railway variables set LLM_MODEL=anthropic/claude-3-5-sonnet
railway variables set ANTHROPIC_API_KEY=your_key

# Deploy
railway up
```

### Render Deployment

1. Create `render.yaml`:

```yaml
services:
  - type: web
    name: incidentiq-api
    env: docker
    dockerfilePath: ./Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: incidentiq-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: incidentiq-redis
          type: redis
          property: connectionString

databases:
  - name: incidentiq-db
    plan: starter
```

2. Push to GitHub
3. Connect to Render
4. Deploy

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes 1.20+
- kubectl configured
- Helm 3.0+

### Step 1: Create Namespace

```bash
kubectl create namespace incidentiq
```

### Step 2: Create Secrets

```bash
kubectl create secret generic incidentiq-secrets \
  --from-literal=db-password=your_password \
  --from-literal=anthropic-api-key=your_key \
  --from-literal=openai-api-key=your_key \
  -n incidentiq
```

### Step 3: Deploy Services

```bash
# Apply manifests
kubectl apply -f k8s/ -n incidentiq

# Or use Helm
helm install incidentiq ./helm -n incidentiq
```

### Step 4: Verify Deployment

```bash
kubectl get pods -n incidentiq
kubectl get services -n incidentiq
```

---

## Monitoring & Logging

### Health Checks

All services expose health endpoints:

```bash
# API health
curl http://localhost/health

# Qdrant health
curl http://localhost:6333

# PostgreSQL health
docker-compose exec postgres pg_isready
```

### Log Aggregation

Configure structured logging output:

```bash
# Docker logs to file
docker-compose logs -f > logs/app.log

# Or use external service
# - Datadog
# - New Relic
# - Elastic Stack
```

### Metrics

Expose Prometheus metrics:

```python
# Add to main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

---

## Backup & Restore

### PostgreSQL Backup

```bash
# Backup
docker-compose exec postgres pg_dump \
  -U incidentiq incidentiq > backup.sql

# Restore
docker-compose exec -T postgres psql \
  -U incidentiq incidentiq < backup.sql
```

### Qdrant Backup

```bash
# Create snapshot
curl -X POST 'http://localhost:6333/collections/incidents/snapshots'

# Download snapshot
curl 'http://localhost:6333/collections/incidents/snapshots/snapshot_name' \
  --output snapshot.dat
```

### Redis Backup

```bash
# Create backup
docker-compose exec redis redis-cli BGSAVE

# Copy backup file
docker cp incidentiq_redis:/data/dump.rdb ./backup/
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose logs api
docker-compose logs postgres

# Check resource usage
docker stats
```

### Database Connection Issues

```bash
# Test connection
docker-compose exec postgres psql -U incidentiq -c "SELECT 1;"

# Check connection pool
docker-compose exec api python -c "
import asyncio
from src.db.models import get_engine
engine = asyncio.run(get_engine())
print(engine.pool.status())
"
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Reduce limits in docker-compose.yml
# Or increase host resources
```

---

## Cost Optimization

### LLM Costs

- Use semantic caching (40-70% savings)
- Use cheaper models for non-critical tasks
- Batch embed requests
- Cache embeddings

### Infrastructure Costs

| Component | Optimization |
|-----------|--------------|
| **Qdrant** | Self-host vs cloud (save $16/mo) |
| **PostgreSQL** | Managed vs self-hosted |
| **Redis** | Enable eviction, limit memory |
| **Compute** | Right-size containers |

**Estimated Monthly Costs**:
- Dev: $0-25
- Production (100 users): $200-500
- Enterprise (1000+ users): $500-2000

---

## Next Steps

- [Configuration Guide](configuration.md) - Detailed configuration
- [Architecture](architecture.md) - System design
- [API Reference](api_reference.md) - API documentation
