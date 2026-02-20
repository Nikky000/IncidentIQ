# API Reference

Complete REST API documentation for IncidentIQ.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently no authentication (add JWT/API keys as needed).

---

## Endpoints

### Health Check

Check service health and status.

```
GET /health
```

**Response** (200 OK):
```json
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

---

### Search Similar Incidents

Find similar incidents based on query.

```
POST /api/v1/search
```

**Request Body**:
```json
{
  "query": "database connection timeout on postgresql",
  "limit": 5,
  "filters": {
    "service": "api-gateway",
    "severity": "high",
    "environment": "production"
  }
}
```

**Parameters**:
- `query` (string, required): Search query
- `limit` (integer, optional): Max results (default: 5)
- `filters` (object, optional): Filter conditions

**Response** (200 OK):
```json
{
  "query": "database connection timeout on postgresql",
  "total_matches": 2,
  "exact_matches": 1,
  "partial_matches": 1,
  "latency_ms": 150,
  "matches": [
    {
      "incident_id": "INC-234",
      "title": "PostgreSQL Connection Pool Exhausted",
      "description": "Max connections reached causing timeouts",
      "similarity_score": 0.95,
      "confidence": "EXACT",
      "error_type": "DatabaseError",
      "service": "api-gateway",
      "severity": "high",
      "resolved_by": "john_doe",
      "resolved_by_contact": "john@company.com",
      "resolution_summary": "Increased max_connections from 100 to 200",
      "resolution_commands": [
        "ALTER SYSTEM SET max_connections = 200;",
        "SELECT pg_reload_conf();"
      ],
      "resolution_time_minutes": 23,
      "rca_document_url": "https://docs.company.com/rca/inc-234",
      "runbook_url": "https://docs.company.com/runbooks/postgres",
      "conversation_url": "slack://channel/C123/p456",
      "match_reasons": [
        "Same error type: DatabaseError",
        "Same service: api-gateway",
        "Keywords match: connection, timeout, postgresql"
      ],
      "created_at": "2024-01-15T08:30:00Z",
      "resolved_at": "2024-01-15T08:53:00Z"
    }
  ]
}
```

**Error Responses**:

```json
// 400 Bad Request
{
  "error": "INVALID_REQUEST",
  "message": "Query parameter is required"
}

// 429 Too Many Requests
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded",
  "retry_after": 60
}

// 503 Service Unavailable
{
  "error": "SERVICE_UNAVAILABLE",
  "message": "Vector database is unavailable"
}
```

---

### Create/Index Incident

Index a new incident for future searching.

```
POST /api/v1/incidents
```

**Request Body**:
```json
{
  "id": "INC-001",
  "title": "Database Connection Timeout",
  "description": "PostgreSQL connections are timing out after 30 seconds",
  "error_message": "psycopg2.OperationalError: connection timeout",
  "error_type": "DatabaseError",
  "error_stack_trace": "Traceback...",
  "service": "api-gateway",
  "environment": "production",
  "severity": "high",
  "status": "resolved",
  "resolved_by": "john_doe",
  "resolved_by_contact": "john@company.com, +1-555-1234",
  "resolution_summary": "Increased connection pool size from 10 to 50",
  "resolution_commands": [
    "ALTER SYSTEM SET max_connections = 50;"
  ],
  "resolution_time_minutes": 23,
  "rca_document_url": "https://docs.company.com/rca/inc-001",
  "runbook_url": "https://docs.company.com/runbooks/database",
  "conversation_url": "slack://channel/C123/p456",
  "keywords": ["database", "timeout", "postgresql", "connection"],
  "symptoms": ["slow queries", "connection errors", "timeouts"],
  "labels": {
    "team": "platform",
    "priority": "P1"
  }
}
```

**Required Fields**:
- `title`: Incident title
- `description`: Detailed description

**Optional Fields**:
- All others are optional but recommended for better matching

**Response** (200 OK):
```json
{
  "status": "indexed",
  "incident_id": "INC-001",
  "embedding_id": "emb_abc123"
}
```

**Error Responses**:
```json
// 400 Bad Request
{
  "error": "INVALID_REQUEST",
  "message": "Title is required"
}
```

---

### Get Incident by ID

Retrieve a specific incident.

```
GET /api/v1/incidents/{incident_id}
```

**Response** (200 OK):
```json
{
  "id": "INC-001",
  "title": "Database Connection Timeout",
  "description": "...",
  // ... all incident fields
}
```

**Error Responses**:
```json
// 404 Not Found
{
  "error": "NOT_FOUND",
  "message": "Incident INC-001 not found"
}
```

---

### Update Incident Feedback

Provide feedback on search results.

```
POST /api/v1/feedback
```

**Request Body**:
```json
{
  "search_id": "search_123",
  "incident_id": "INC-001",
  "was_helpful": true,
  "feedback_comment": "This solution worked perfectly!",
  "user_id": "U123456"
}
```

**Response** (200 OK):
```json
{
  "status": "recorded"
}
```

---

### Get Statistics

Get platform statistics.

```
GET /api/v1/stats
```

**Response** (200 OK):
```json
{
  "total_incidents": 1234,
  "total_searches": 5678,
  "avg_search_latency_ms": 150,
  "cache_hit_rate": 0.65,
  "top_services": [
    {"service": "api-gateway", "count": 234},
    {"service": "payment-service", "count": 189}
  ],
  "top_error_types": [
    {"error_type": "DatabaseError", "count": 456},
    {"error_type": "TimeoutError", "count": 234}
  ],
  "resolution_time_stats": {
    "avg_minutes": 45,
    "median_minutes": 30,
    "p95_minutes": 120
  }
}
```

---

### Find Experts

Find experts for a specific topic.

```
POST /api/v1/experts/search
```

**Request Body**:
```json
{
  "query": "postgresql performance issues",
  "service": "database",
  "limit": 5
}
```

**Response** (200 OK):
```json
{
  "experts": [
    {
      "user_id": "john_doe",
      "display_name": "John Doe",
      "email": "john@company.com",
      "phone": "+1-555-1234",
      "platform": "slack",
      "incidents_resolved": 42,
      "avg_resolution_time_minutes": 35,
      "skills": [
        {
          "skill_type": "service",
          "skill_name": "postgresql",
          "proficiency_score": 9.5,
          "incident_count": 15
        }
      ],
      "timezone": "America/New_York",
      "available": true,
      "last_active_at": "2024-02-05T10:30:00Z"
    }
  ]
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/v1/search` | 30 requests/minute per user |
| `/api/v1/incidents` (POST) | 10 requests/minute per user |
| All other endpoints | 60 requests/minute per user |

**Rate Limit Headers**:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1612540800
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Malformed request or missing required fields |
| `NOT_FOUND` | Resource not found |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `SERVICE_UNAVAILABLE` | External service (LLM, Qdrant) unavailable |
| `TIMEOUT_ERROR` | Request timed out |
| `CONFIGURATION_ERROR` | Server configuration error |
| `INTERNAL_ERROR` | Unexpected server error |

---

## Webhooks

### Slack Events

IncidentIQ can receive Slack events via webhook:

```
POST /webhooks/slack/events
```

**Handled Events**:
- `message`: War room message
- `app_mention`: Bot mention
- `reaction_added`: Feedback reactions

---

## Next Steps

- [Configuration Guide](configuration.md) - Setup instructions
- [Development Guide](development.md) - Local development
- [Testing Guide](testing.md) - API testing
