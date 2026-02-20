# ============================================
# IncidentIQ Development Makefile
# ============================================

.PHONY: help install dev test lint docker-up docker-down clean

# Default target
help:
	@echo "IncidentIQ Development Commands"
	@echo "================================"
	@echo "make install      - Install dependencies"
	@echo "make dev          - Start development server"
	@echo "make test         - Run tests"
	@echo "make lint         - Run linter"
	@echo "make docker-up    - Start all services with Docker"
	@echo "make docker-down  - Stop Docker services"
	@echo "make docker-build - Build Docker images"
	@echo "make clean        - Clean up"

# ============================================
# Development
# ============================================

install:
	pip install -e ".[dev]"
	@echo "✅ Dependencies installed"

dev:
	@echo "🚀 Starting development server..."
	python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-bot:
	@echo "🤖 Starting Slack bot..."
	python -m src.bots.slack_bot

# ============================================
# Testing
# ============================================

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-fast:
	pytest tests/ -x -v

# ============================================
# Linting & Formatting
# ============================================

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

# ============================================
# Docker
# ============================================

docker-build:
	docker-compose build

docker-up:
	@echo "🐳 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "   API: http://localhost:8000"
	@echo "   Qdrant: http://localhost:6333"
	@echo "   Redis: localhost:6379"
	@echo "   PostgreSQL: localhost:5432"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

# ============================================
# Database
# ============================================

db-migrate:
	@echo "Running database migrations..."
	python -c "import asyncio; from src.db.models import init_db; asyncio.run(init_db())"

db-shell:
	docker-compose exec postgres psql -U incidentiq -d incidentiq

# ============================================
# Production
# ============================================

prod-up:
	docker-compose -f docker-compose.yml up -d --scale api=2

prod-down:
	docker-compose -f docker-compose.yml down

# ============================================
# Cleanup
# ============================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	@echo "🧹 Cleaned up!"

clean-docker:
	docker-compose down -v --remove-orphans
	docker system prune -f
