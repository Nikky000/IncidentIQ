# Configuration Guide

Complete guide to configuring IncidentIQ for your environment.

## Configuration Methods

IncidentIQ supports two configuration methods:

1. **Environment Variables** (`.env` file) - For deployment settings
2. **Database-Backed Config** - For runtime settings

### Priority Order

1. Environment variable (if set)
2. Database configuration
3. Default value

## Environment Variables

### Required Variables

```bash
# Database (REQUIRED)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/incidentiq

# Redis Cache (REQUIRED)
REDIS_URL=redis://localhost:6379/0

# Vector Database (REQUIRED)
QDRANT_URL=http://localhost:6333
```

### LLM Providers

#### OpenAI

```bash
LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-...

# Embedding
EMBEDDING_MODEL=openai/text-embedding-3-small
```

#### Anthropic (Claude)

```bash
LLM_MODEL=anthropic/claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...

# Embedding (use OpenAI or other)
EMBEDDING_MODEL=openai/text-embedding-3-small
OPENAI_API_KEY=sk-...
```

#### Azure OpenAI

```bash
LLM_MODEL=azure/gpt-4
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com
AZURE_API_VERSION=2024-02-15-preview

# Embedding
EMBEDDING_MODEL=azure/text-embedding-ada-002
```

#### Ollama (Local, FREE)

```bash
LLM_MODEL=ollama/llama2
LLM_API_BASE=http://localhost:11434

# Embedding (use local model)
EMBEDDING_MODEL=ollama/nomic-embed-text
```

#### Custom Enterprise Endpoint

```bash
LLM_MODEL=openai/your-custom-model
LLM_API_BASE=https://your-company-llm.com/v1
OPENAI_API_KEY=your_enterprise_key
```

### Slack Bot

```bash
# Slack App credentials
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...

# Learning channel (war room)
SLACK_WAR_ROOM_CHANNEL=C123456789
```

### Optional Settings

```bash
# Application
APP_ENV=production  # development, staging, production
DEBUG=false
LOG_LEVEL=INFO

# Pattern Matching Thresholds
EXACT_MATCH_THRESHOLD=0.92
PARTIAL_MATCH_THRESHOLD=0.70
MIN_MATCH_THRESHOLD=0.50
MAX_SIMILAR_INCIDENTS=5

# LLM Settings
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2000
LLM_TIMEOUT=30

# Semantic Caching
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_THRESHOLD=0.95

# Database
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Security
CORS_ORIGINS=["http://localhost:3000"]
```

## Database-Backed Configuration

For settings that change frequently, use database configuration.

### Setting Values

```python
from src.db.config_service import get_db_config_service

config = await get_db_config_service()

# Set exact match threshold
await config.set(
    key="EXACT_MATCH_THRESHOLD",
    value=0.95,
    value_type="float",
    changed_by="admin",
    reason="Increased precision requirements"
)
```

### Getting Values

```python
# Get value (checks DB, then env, then default)
threshold = await config.get("EXACT_MATCH_THRESHOLD", default=0.92)

# Get all values with prefix
llm_config = await config.get_all(prefix="LLM_")
```

### Audit Trail

All configuration changes are logged in `configuration_history` table with:
- Who changed it
- When it changed
- Old value
- New value
- Reason for change

## Slack Bot Setup

### 1. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "IncidentIQ" and select workspace

### 2. Configure Bot Permissions

**OAuth & Permissions** → **Bot Token Scopes**:

```
app_mentions:read
channels:history
channels:read
chat:write
commands
users:read
```

### 3. Enable Socket Mode

**Socket Mode** → Enable Socket Mode

Generate app-level token with scope `connections:write`

### 4. Install to Workspace

**Install App** → Install to workspace

Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 5. Add Slash Commands

**Slash Commands** → Create commands:

| Command | Description |
|---------|-------------|
| `/incidentiq search` | Search similar incidents |
| `/incidentiq help` | Show help |

### 6. Set Environment Variables

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
```

### 7. Invite Bot to Channel

In your war room channel:
```
/invite @IncidentIQ
```

## Vector Database (Qdrant)

### Cloud (Free Tier)

```bash
# Sign up at qdrant.cloud
QDRANT_URL=https://your-cluster.qdrant.cloud
QDRANT_API_KEY=your_api_key
```

### Self-Hosted (Docker)

```bash
# Already included in docker-compose.yml
QDRANT_URL=http://qdrant:6333
```

### Custom Instance

```bash
QDRANT_URL=http://your-qdrant-server:6333
QDRANT_API_KEY=optional_api_key
```

## PostgreSQL

### Local Development

```bash
DATABASE_URL=postgresql+asyncpg://incidentiq:password@localhost:5432/incidentiq
```

### Production (with SSL)

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

### Connection Pool Settings

```bash
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
```

## Redis

### Local Development

```bash
REDIS_URL=redis://localhost:6379/0
```

### Production (with password)

```bash
REDIS_URL=redis://:password@host:6379/0
```

### Redis Cloud

```bash
REDIS_URL=redis://default:password@redis-12345.cloud.redislabs.com:12345
```

## Pattern Matching Configuration

### Threshold Tuning

```bash
# Higher = more strict (fewer false positives)
EXACT_MATCH_THRESHOLD=0.92

# Lower = more lenient (more matches)
EXACT_MATCH_THRESHOLD=0.88
```

**Recommendations**:
- Start with default (0.92)
- Monitor false positive rate
- Adjust based on feedback

### Hybrid Search Weights

Configure in database:

```python
await config.set("VECTOR_WEIGHT", 0.70, "float")
await config.set("SERVICE_WEIGHT", 0.15, "float")
await config.set("ERROR_TYPE_WEIGHT", 0.10, "float")
await config.set("KEYWORD_WEIGHT", 0.05, "float")
```

## Security Configuration

### CORS Origins

```bash
CORS_ORIGINS=["https://your-dashboard.com", "http://localhost:3000"]
```

### Rate Limiting

Configure in database:

```python
# Searches per user per minute
await config.set("RATE_LIMIT_SEARCH_USER", 30, "int")

# LLM calls per user per minute
await config.set("RATE_LIMIT_LLM_USER", 20, "int")
```

## Logging

### Log Level

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Structured Logging

Logs are in JSON format:

```json
{
  "timestamp": "2024-02-05T12:00:00Z",
  "level": "INFO",
  "message": "Incident indexed",
  "incident_id": "INC-001",
  "request_id": "req-123"
}
```

## Health Checks

All services expose health endpoints:

```bash
# API
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "postgres": "ok",
    "redis": "ok",
    "qdrant": "ok"
  }
}
```

## Troubleshooting

### LLM Connection Issues

```bash
# Test LLM connectivity
export LLM_MODEL=openai/gpt-4o
export OPENAI_API_KEY=sk-...

python -c "
from litellm import completion
response = completion(
    model='openai/gpt-4o',
    messages=[{'role': 'user', 'content': 'test'}]
)
print(response.choices[0].message.content)
"
```

### Database Connection Issues

```bash
# Test database connectivity
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    engine = create_async_engine('postgresql+asyncpg://...')
    async with engine.connect() as conn:
        print('Connected!')

asyncio.run(test())
"
```

### Qdrant Connection Issues

```bash
# Test Qdrant connectivity
curl http://localhost:6333/collections
```

## Next Steps

- [API Reference](api_reference.md) - Endpoint documentation
- [Development Guide](development.md) - Developer setup
- [Deployment Guide](deployment.md) - Production deployment
