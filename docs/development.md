# Development Guide

## Local Development Setup

### Prerequisites

- Python 3.11+
- uv (package manager)
- Docker & Docker Compose (optional)
- PostgreSQL (optional, for database tests)

### Installation

```bash
# Clone repository
cd /Users/dileshchouhan/zysecai/LeadTheAI/devops/incidentiq

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
```

### Environment Configuration

Edit `.env` with your API keys:

```bash
# Choose your LLM provider
LLM_MODEL=anthropic/claude-3-5-sonnet
ANTHROPIC_API_KEY=sk-ant-...

# Or use OpenAI
LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-...

# Or use local Ollama (FREE)
LLM_MODEL=ollama/llama2
LLM_API_BASE=http://localhost:11434

# Embedding
EMBEDDING_MODEL=openai/text-embedding-3-small
```

---

## Running Services

### Option 1: Docker (Recommended)

```bash
# Start all services
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

Services available at:
- API: http://localhost:80
- Qdrant: http://localhost:6333
- PostgreSQL: localhost:5432

### Option 2: Local Development

```bash
# Start dependencies with Docker
docker-compose up -d postgres redis qdrant

# Run API
make dev

# Or manually
uvicorn src.api.main:app --reload
```

### Option 3: Slack Bot

```bash
# Configure Slack credentials in .env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...

# Run bot
python -m src.bots.slack_bot
```

---

## Development Workflow

### 1. Make Changes

Edit files in `src/`:

```
src/
├── core/           # Pattern matching, config, utils
├── services/       # LLM, cache services
├── db/             # Database models
├── api/            # FastAPI endpoints
└── bots/           # Slack bot
```

### 2. Run Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_pattern_matching.py -v

# With coverage
pytest --cov=src --cov-report=html
```

### 3. Lint & Format

```bash
# Lint
make lint

# Or manually
ruff check src tests

# Auto-fix
ruff check --fix src tests
```

### 4. Type Check

```bash
mypy src
```

---

## Project Structure

```
incidentiq/
├── src/
│   ├── core/
│   │   ├── config.py          # Settings
│   │   ├── pattern_matching.py # THE USP
│   │   └── utils.py            # Circuit breaker, rate limiter
│   ├── services/
│   │   ├── llm_service.py     # LLM & embeddings
│   │   └── cache_service.py   # Redis caching
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   └── config_service.py  # DB-backed config
│   ├── api/
│   │   └── main.py             # FastAPI app
│   └── bots/
│       └── slack_bot.py        # Slack integration
├── tests/                      # Test suite
├── docs/                       # Documentation
├── config/                     # Nginx config
├── scripts/                    # DB init scripts
├── Dockerfile                  # Production image
├── docker-compose.yml          # Full stack
├── Makefile                    # Dev commands
└── pyproject.toml              # Dependencies
```

---

## Makefile Commands

```bash
make install      # Install dependencies
make dev          # Run dev server
make test         # Run tests
make test-fast    # Run tests (stop on first failure)
make lint         # Run linter
make docker-up    # Start Docker stack
make docker-down  # Stop Docker stack
make docker-logs  # View logs
make clean        # Clean cache files
```

---

## Database Management

### Migrations

```python
# Create tables
from src.db.models import create_tables
await create_tables()

# Or use SQL script
docker-compose exec postgres psql -U incidentiq -f /scripts/init-db.sql
```

### Querying

```python
from src.db.models import get_session
from src.db.models import Incident

async with get_session() as session:
    incidents = await session.execute(
        select(Incident).where(Incident.service == "api-gateway")
    )
```

---

## Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG python -m src.api.main
```

### Interactive Shell

```python
# Test LLM service
from src.services.llm_service import LLMService
from src.core.config import get_settings

settings = get_settings()
llm = LLMService(settings)

response = await llm.complete([
    {"role": "user", "content": "Hello"}
])
print(response)
```

### Check Circuit Breaker State

```python
from src.core.utils import circuit_breakers

for name, breaker in circuit_breakers.items():
    print(f"{name}: {breaker.state}")
```

---

## Common Issues

### Import Errors

```bash
# Ensure you're in the virtual environment
source .venv/bin/activate

# Reinstall in editable mode
uv pip install -e .
```

### Database Connection

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql postgresql://incidentiq:password@localhost:5432/incidentiq
```

### Redis Connection

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli -h localhost ping
```

---

## Adding New Features

### 1. Add Core Logic

```python
# src/core/my_feature.py
class MyFeature:
    def __init__(self, settings):
        self.settings = settings
    
    async def process(self):
        # Your logic here
        pass
```

### 2. Add Tests

```python
# tests/test_my_feature.py
import pytest

@pytest.mark.asyncio
async def test_my_feature():
    feature = MyFeature(test_settings)
    result = await feature.process()
    assert result is not None
```

### 3. Add API Endpoint

```python
# src/api/main.py
@app.post("/api/v1/my-endpoint")
async def my_endpoint():
    feature = MyFeature(get_settings())
    return await feature.process()
```

### 4. Update Documentation

```bash
# Update docs/api_reference.md
# Add endpoint documentation
```

---

## Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)
```

---

## Next Steps

- [Testing Guide](testing.md) - How to test
- [Deployment Guide](deployment.md) - Production deployment
- [Configuration Guide](configuration.md) - All settings
