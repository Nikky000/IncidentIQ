# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Chat Platforms                            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  Slack   │    │  Teams   │    │  GChat   │                  │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                  │
└───────┼──────────────┼──────────────┼─────────────────────────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │      FastAPI Backend        │
        │  ┌────────────────────────┐ │
        │  │   Pattern Matching     │ │
        │  │   Engine (USP)         │ │
        │  │  - Hybrid search       │ │
        │  │  - Confidence scoring  │ │
        │  │  - Explainability      │ │
        │  └────────────────────────┘ │
        │  ┌────────────────────────┐ │
        │  │   LLM Service          │ │
        │  │  - LiteLLM             │ │
        │  │  - Semantic caching    │ │
        │  │  - Fallback            │ │
        │  └────────────────────────┘ │
        │  ┌────────────────────────┐ │
        │  │   Embedding Service    │ │
        │  │  - Batch processing    │ │
        │  │  - Caching             │ │
        │  └────────────────────────┘ │
        └──┬────┬────┬────┬──────────┘
           │    │    │    │
    ┌──────▼┐ ┌─▼───┐ ┌──▼────┐ ┌────▼────┐
    │Qdrant │ │Redis│ │Postgres│ │ Nginx  │
    │Vector │ │Cache│ │  DB    │ │  LB    │
    └───────┘ └─────┘ └────────┘ └─────────┘
```

## Core Components

### 1. Pattern Matching Engine (THE USP)

**Location**: `src/core/pattern_matching.py`

The pattern matching engine is the unique selling point of IncidentIQ. It uses precision-tiered matching to provide honest, reliable incident recommendations.

**Key Features**:
- **Hybrid Search**: Combines vector similarity + keyword matching
- **Precision Tiers**:
  - `EXACT` (≥92%): High confidence, recommend action
  - `PARTIAL` (70-92%): Reference only, not definitive
  - `NONE` (<70%): No match found, escalate
- **Explainability**: Shows WHY incidents matched
- **Confidence Scoring**: Transparent about certainty

**Algorithm**:
```python
1. Generate embedding for query
2. Vector search in Qdrant (top 20)
3. Re-rank with hybrid scoring:
   - Vector similarity (70% weight)
   - Service match (15% weight)
   - Error type match (10% weight)
   - Keyword overlap (5% weight)
4. Calculate confidence tier
5. Generate explanation
```

### 2. LLM Service

**Location**: `src/services/llm_service.py`

Vendor-agnostic LLM integration using LiteLLM.

**Features**:
- Supports 100+ LLM providers
- Automatic fallback (primary → secondary)
- Semantic caching (40-70% cost reduction)
- Streaming responses
- Circuit breaker for reliability

**Supported Providers**:
- OpenAI (GPT-4, GPT-4o)
- Anthropic (Claude)
- Azure OpenAI
- Ollama (local, FREE)
- Custom endpoints

### 3. Embedding Service

**Location**: `src/services/llm_service.py`

Efficient embedding generation with caching.

**Features**:
- Batch processing (up to 100 texts)
- Embedding cache (avoid re-processing)
- Cost optimization
- Multiple provider support

### 4. Database Layer

**Location**: `src/db/`

**Models**:
- `Incident`: Full incident metadata
- `Expert`: Who-knows-what mapping
- `ExpertSkill`: Expertise tracking
- `Configuration`: DB-backed settings
- `SearchLog`: Analytics and feedback

**Features**:
- Connection pooling (max 20 connections)
- Async operations
- Auto-timestamps
- Full-text search indexes

### 5. Cache Service

**Location**: `src/services/cache_service.py`

Redis-based caching for performance.

**Features**:
- Standard key-value cache
- Semantic caching for LLM responses
- TTL support
- Embedding cache

## Data Flow

### Incident Indexing

```
1. Slack message → Extract incident details
2. LLM analyzes context → Structured data
3. Generate embedding → Vector representation
4. Store in Qdrant + PostgreSQL
5. Update expert graph
```

### Incident Search

```
1. User query → Parse and clean
2. Generate query embedding
3. Hybrid search in Qdrant
4. Re-rank results
5. Calculate confidence tiers
6. Generate explanations
7. Format response
```

## Reliability Features

### Circuit Breaker

**Location**: `src/core/utils.py`

Prevents cascade failures by failing fast when services are down.

**States**:
- `CLOSED`: Normal operation
- `OPEN`: Service failing, reject requests
- `HALF_OPEN`: Testing if service recovered

**Thresholds**:
- LLM: 5 failures → open (30s reset)
- Embedding: 5 failures → open (30s reset)
- Qdrant: 3 failures → open (60s reset)

### Rate Limiter

**Location**: `src/core/utils.py`

Token bucket rate limiting per user/channel.

**Limits**:
- Search per user: 30 req/60s
- Search per channel: 100 req/60s
- LLM per user: 20 req/60s

### Error Handling

**Custom Exceptions**:
- `IncidentIQError`: Base exception
- `RateLimitError`: Rate limit exceeded
- `ServiceUnavailableError`: External service down
- `ConfigurationError`: Config issue

## Scalability

### Horizontal Scaling

```bash
# Scale API servers
docker-compose up -d --scale api=5

# Scale bot workers
docker-compose up -d --scale slack-bot=2
```

### Load Balancing

Nginx load balancer with:
- Least connections algorithm
- Health checks
- Rate limiting
- Connection limits

### Database Optimization

- Connection pooling (20 connections)
- Indexes on frequently queried fields
- Full-text search indexes
- JSONB for flexible metadata

## Performance

### Typical Latencies

| Operation | Latency |
|-----------|---------|
| Vector search | 50-100ms |
| Hybrid search | 100-200ms |
| LLM call (cached) | 5-10ms |
| LLM call (uncached) | 2-5s |
| Embedding generation | 100-300ms |

### Cache Hit Rates

| Cache Type | Expected Hit Rate |
|------------|------------------|
| Semantic LLM cache | 40-70% |
| Embedding cache | 60-80% |
| Standard cache | 80-90% |

## Security

### Container Security

- Non-root user in Docker
- Minimal base image
- No secrets in image

### Network Security

- Nginx with security headers
- Rate limiting
- CORS configuration

### Data Security

- Encrypted secrets in database
- Audit logging for config changes
- Connection encryption (TLS)

## Monitoring

### Health Checks

All services have health checks:
- API: `/health`
- PostgreSQL: `pg_isready`
- Redis: `PING`
- Qdrant: HTTP check

### Logging

Structured JSON logs with:
- Request ID
- User context
- Performance metrics
- Error traces

## Next Steps

- [Configuration Guide](configuration.md) - Setup instructions
- [API Reference](api_reference.md) - Endpoint documentation
- [Development Guide](development.md) - Developer workflow
