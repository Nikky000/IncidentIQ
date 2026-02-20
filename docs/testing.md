# Testing Guide

## Running Tests

### Quick Start

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# With coverage
pytest --cov=src --cov-report=html
```

---

## Test Results

**Current Status**: ✅ **31/36 tests passing (86%)**

### Passing Tests (31)

| Test Suite | Tests | Status |
|------------|-------|--------|
| API Endpoints | 4/4 | ✅ All passing |
| LLM Service | 7/7 | ✅ All passing |
| Pattern Matching | 10/10 | ✅ All passing |
| Utils (Circuit Breaker, Rate Limiter) | 10/10 | ✅ All passing |
| **Database Tests** | 0/5 | ⚠️ Require PostgreSQL |

### Database Test Errors (5)

The 5 database tests fail with SQLite because they use PostgreSQL-specific types (`ARRAY`).

**Solution**: Run database tests with PostgreSQL:

```bash
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Run tests with PostgreSQL
DATABASE_URL=postgresql+asyncpg://incidentiq:password@localhost:5432/incidentiq pytest tests/test_database.py -v
```

Or skip database tests:

```bash
pytest tests/ -v --ignore=tests/test_database.py
```

---

## Test Coverage

### Unit Tests

- ✅ Pattern matching engine
- ✅ LLM service with caching
- ✅ Embedding service
- ✅ Circuit breaker (all states)
- ✅ Rate limiter
- ✅ Custom exceptions

### Integration Tests

- ✅ API endpoints (FastAPI)
- ⚠️ Database models (requires PostgreSQL)

---

## Writing New Tests

### Test Structure

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_my_feature(sample_incident_data):
    """Test description"""
    # Arrange
    mock_service = AsyncMock()
    
    # Act
    result = await my_function(mock_service)
    
    # Assert
    assert result is not None
```

### Available Fixtures

From `tests/conftest.py`:

- `test_settings`: Test configuration
- `db_engine`: Async database engine
- `db_session`: Async database session
- `mock_llm_response`: Mock LLM response
- `mock_embedding`: Mock embedding vector
- `sample_incident_data`: Sample incident dictionary

---

## Continuous Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv pip install -e ".[dev]"
      
      - name: Run tests
        run: pytest tests/ -v --cov=src
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test
```

---

## Test Commands

```bash
# Run specific test file
pytest tests/test_pattern_matching.py -v

# Run specific test
pytest tests/test_pattern_matching.py::test_calculate_confidence_exact -v

# Fast fail (stop on first failure)
pytest tests/ -x

# Run with coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Run only unit tests (skip integration)
pytest tests/ -v -m "not integration"
```

---

## Mocking External Services

### LLM Service

```python
@patch('src.services.llm_service.acompletion')
async def test_with_llm(mock_acompletion):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "test response"
    mock_acompletion.return_value = mock_response
    
    # Your test here
```

### Qdrant

```python
@patch('src.core.pattern_matching.AsyncQdrantClient')
async def test_with_qdrant(mock_qdrant):
    mock_client = AsyncMock()
    mock_client.search.return_value = [...]
    mock_qdrant.return_value = mock_client
    
    # Your test here
```

---

## Next Steps

- [Development Guide](development.md) - Local development
- [API Reference](api_reference.md) - API documentation
- [Deployment Guide](deployment.md) - Production deployment
