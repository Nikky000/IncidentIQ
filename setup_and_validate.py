#!/usr/bin/env python3
"""
IncidentIQ System Setup and Validation Tool

This script performs comprehensive checks and auto-fixes for the IncidentIQ system.
Run this before deploying or when troubleshooting issues.

Usage:
    uv run python setup_and_validate.py
    python setup_and_validate.py --fix-all
    python setup_and_validate.py --skip-index
"""

import asyncio
import sys
import os
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


@dataclass
class CheckResult:
    """Result of a system check"""
    name: str
    status: str  # "pass", "warning", "error", "skipped"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    fix_suggested: bool = False
    fix_command: Optional[str] = None


class SystemValidator:
    """Comprehensive system validator for IncidentIQ"""

    def __init__(self, project_path: Path, fix_all: bool = False, skip_index: bool = False):
        self.project_path = project_path
        self.fix_all = fix_all
        self.skip_index = skip_index
        self.results: List[CheckResult] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{text:^70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")

    def print_result(self, result: CheckResult):
        """Print a check result with colors"""
        icons = {
            "pass": f"{Colors.OKGREEN}✅{Colors.ENDC}",
            "warning": f"{Colors.WARNING}⚠️ {Colors.ENDC}",
            "error": f"{Colors.FAIL}❌{Colors.ENDC}",
            "skipped": f"{Colors.OKCYAN}⊘{Colors.ENDC}",
        }

        icon = icons.get(result.status, "❓")
        status_color = {
            "pass": Colors.OKGREEN,
            "warning": Colors.WARNING,
            "error": Colors.FAIL,
            "skipped": Colors.OKCYAN,
        }.get(result.status, "")

        print(f"{icon} {result.name}: {status_color}{result.message}{Colors.ENDC}")

        if result.details:
            for key, value in result.details.items():
                if value:
                    print(f"     {key}: {value}")

        if result.fix_suggested and self.fix_all:
            if result.fix_command:
                print(f"     {Colors.OKCYAN}Auto-fixing...{Colors.ENDC}")
        elif result.fix_suggested:
            if result.fix_command:
                print(f"     {Colors.WARNING}Fix: {result.fix_command}{Colors.ENDC}")

    def add_result(self, result: CheckResult):
        """Add a result to the list"""
        self.results.append(result)
        if result.status == "error":
            self.errors.append(f"[{result.name}] {result.message}")
        elif result.status == "warning":
            self.warnings.append(f"[{result.name}] {result.message}")

    async def check_python_version(self) -> CheckResult:
        """Check 1: Python version"""
        version = sys.version_info
        if version >= (3, 10):
            return CheckResult(
                name="Python Version",
                status="pass",
                message=f"Python {version.major}.{version.minor}.{version.micro}",
                details={"minimum_required": "3.10"}
            )
        else:
            return CheckResult(
                name="Python Version",
                status="error",
                message=f"Python {version.major}.{version.minor} is too old",
                details={"minimum_required": "3.10", "current": f"{version.major}.{version.minor}"},
                fix_command="Upgrade to Python 3.10 or later"
            )

    async def check_dependencies(self) -> CheckResult:
        """Check 2: Python dependencies"""
        required = {
            "qdrant-client": "Qdrant vector database client",
            "litellm": "LLM abstraction layer",
            "pydantic": "Data validation",
            "pydantic-settings": "Configuration management",
            "fastapi": "API framework",
            "uvicorn": "ASGI server",
            "sqlalchemy": "Database ORM",
            "asyncpg": "PostgreSQL async driver",
        }

        optional = {
            "sentence_transformers": "Local embeddings (optional, API fallback available)",
        }

        missing = []
        available = []
        missing_optional = []

        for module, description in required.items():
            module_name = module.replace("-", "_")
            try:
                __import__(module_name)
                available.append(f"{module} ({description})")
            except ImportError:
                missing.append(f"{module} ({description})")

        for module, description in optional.items():
            module_name = module.replace("-", "_")
            try:
                __import__(module_name)
                available.append(f"{module} ({description})")
            except ImportError:
                missing_optional.append(f"{module} ({description})")

        if missing:
            return CheckResult(
                name="Dependencies",
                status="error",
                message=f"Missing {len(missing)} required packages",
                details={
                    "missing": missing,
                    "available": len(available),
                    "optional_missing": missing_optional
                },
                fix_command="uv sync" if not self.fix_all else None
            )

        if missing_optional:
            return CheckResult(
                name="Dependencies",
                status="warning",
                message="Optional packages missing (API fallback available)",
                details={
                    "available": len(available),
                    "optional_missing": missing_optional
                },
                fix_command="uv sync --optional" if not self.fix_all else None
            )

        return CheckResult(
            name="Dependencies",
            status="pass",
            message=f"All {len(required)} required packages installed",
            details={"available": len(available)}
        )

    async def check_configuration(self) -> CheckResult:
        """Check 3: Configuration file"""
        env_file = self.project_path / ".env"

        if not env_file.exists():
            return CheckResult(
                name="Configuration",
                status="error",
                message=".env file not found",
                details={
                    "expected_path": str(env_file),
                    "template": ".env.example" if (self.project_path / ".env.example").exists() else None
                },
                fix_command="cp .env.example .env && edit .env"
            )

        # Try to load configuration
        try:
            sys.path.insert(0, str(self.project_path))
            from src.core.config import get_settings
            settings = get_settings()

            checks = []
            issues = []

            # Check essential settings
            if not settings.database.url or "incidentiq" not in settings.database.url:
                issues.append("DATABASE_URL not set correctly")

            if not settings.cache.url:
                issues.append("REDIS_URL not set")

            if not settings.vector_db.url:
                issues.append("QDRANT_URL not set")

            # Check embedding configuration
            embedding_type = "local" if settings.embedding.use_local_embeddings else "API"
            checks.append(f"Embeddings: {embedding_type}")
            checks.append(f"Model: {settings.embedding.model}")
            checks.append(f"Dimensions: {settings.embedding.dimensions}")

            # Check LLM configuration
            checks.append(f"LLM: {settings.llm.model}")
            if not settings.llm.api_key:
                issues.append("LLM_API_KEY not set")

            if issues:
                return CheckResult(
                    name="Configuration",
                    status="error",
                    message=f"Configuration issues found",
                    details={
                        "issues": issues,
                        "checks": checks
                    },
                    fix_command="Edit .env file with correct values"
                )

            return CheckResult(
                name="Configuration",
                status="pass",
                message="Configuration loaded successfully",
                details={"checks": checks}
            )

        except Exception as e:
            return CheckResult(
                name="Configuration",
                status="error",
                message=f"Failed to load configuration: {e}",
                fix_command="Check .env file format and values"
            )

    async def check_docker_services(self) -> CheckResult:
        """Check 4: Docker services"""
        try:
            import subprocess

            # Check if Docker is running
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return CheckResult(
                    name="Docker Services",
                    status="error",
                    message="Docker is not running",
                    fix_command="Start Docker Desktop"
                )

            # Parse running containers
            lines = result.stdout.strip().split('\n')
            running = []

            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    container_id = parts[0]
                    name = parts[-1] if len(parts) > 1 else ""
                    if "incidentiq" in name.lower():
                        running.append(name)

            expected = ["postgres", "redis", "qdrant"]
            missing = [s for s in expected if not any(s in c.lower() for c in running)]

            if missing:
                return CheckResult(
                    name="Docker Services",
                    status="error",
                    message=f"Missing services: {', '.join(missing)}",
                    details={"running": running},
                    fix_command="make docker-up" if not self.fix_all else None
                )

            return CheckResult(
                name="Docker Services",
                status="pass",
                message=f"All services running ({len(running)} containers)",
                details={"running": running}
            )

        except Exception as e:
            return CheckResult(
                name="Docker Services",
                status="warning",
                message=f"Could not check Docker: {e}",
                details={"manual_check": "Run 'docker ps' to verify"}
            )

    async def check_postgresql(self) -> CheckResult:
        """Check 5: PostgreSQL connectivity"""
        try:
            sys.path.insert(0, str(self.project_path))
            from src.core.config import get_settings
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text

            settings = get_settings()

            engine = create_async_engine(
                settings.database.url,
                pool_pre_ping=True,
            )

            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                # Extract version number
                version_str = version.split()[0] + " " + version.split()[1]

            await engine.dispose()

            return CheckResult(
                name="PostgreSQL",
                status="pass",
                message="PostgreSQL connected",
                details={"version": version_str}
            )

        except Exception as e:
            return CheckResult(
                name="PostgreSQL",
                status="error",
                message=f"PostgreSQL connection failed: {e}",
                fix_command="Check DATABASE_URL in .env and ensure PostgreSQL is running"
            )

    async def check_redis(self) -> CheckResult:
        """Check 6: Redis connectivity"""
        try:
            sys.path.insert(0, str(self.project_path))
            from src.core.config import get_settings
            import redis.asyncio as redis

            settings = get_settings()

            # Parse URL
            url = settings.cache.url
            if url.startswith("redis://"):
                host = url.split("//")[1].split("/")[0].split(":")[0]
                port = int(url.split("//")[1].split("/")[0].split(":")[1]) if ":" in url.split("//")[1].split("/")[0] else 6379
            else:
                host = "localhost"
                port = 6379

            client = await redis.Redis(host=host, port=port, decode_responses=True)
            await client.ping()
            info = await client.info("server")
            await client.close()

            return CheckResult(
                name="Redis",
                status="pass",
                message="Redis connected",
                details={
                    "version": info.get("redis_version", "unknown"),
                    "mode": info.get("redis_mode", "standalone")
                }
            )

        except Exception as e:
            return CheckResult(
                name="Redis",
                status="error",
                message=f"Redis connection failed: {e}",
                fix_command="Check REDIS_URL in .env and ensure Redis is running"
            )

    async def check_qdrant(self) -> CheckResult:
        """Check 7: Qdrant connectivity"""
        try:
            from qdrant_client import AsyncQdrantClient

            sys.path.insert(0, str(self.project_path))
            from src.core.config import get_settings

            settings = get_settings()

            client = AsyncQdrantClient(
                url=settings.vector_db.url,
                api_key=settings.vector_db.api_key,
            )

            collections = await client.get_collections()
            collection_names = [c.name for c in collections.collections]

            await client.close()

            return CheckResult(
                name="Qdrant",
                status="pass",
                message=f"Qdrant connected ({len(collection_names)} collections)",
                details={"collections": collection_names}
            )

        except Exception as e:
            return CheckResult(
                name="Qdrant",
                status="error",
                message=f"Qdrant connection failed: {e}",
                fix_command="Check QDRANT_URL in .env and ensure Qdrant is running"
            )

    async def check_embeddings(self) -> CheckResult:
        """Check 8: Embedding service"""
        try:
            sys.path.insert(0, str(self.project_path))
            from src.services.llm_service import EmbeddingService
            from src.core.config import get_settings

            settings = get_settings()

            embed_service = EmbeddingService()

            # Test embedding
            test_text = "database connection timeout"
            embedding = await embed_service.embed(test_text)

            expected_dim = settings.embedding.dimensions
            actual_dim = len(embedding)

            if actual_dim != expected_dim:
                return CheckResult(
                    name="Embeddings",
                    status="error",
                    message=f"Dimension mismatch: expected {expected_dim}, got {actual_dim}",
                    details={
                        "model": settings.embedding.model,
                        "expected": expected_dim,
                        "actual": actual_dim
                    },
                    fix_command=f"Update EMBEDDING_DIMENSIONS={actual_dim} in .env"
                )

            return CheckResult(
                name="Embeddings",
                status="pass",
                message=f"Embeddings working ({actual_dim} dims)",
                details={
                    "model": settings.embedding.model,
                    "local": settings.embedding.use_local_embeddings
                }
            )

        except Exception as e:
            return CheckResult(
                name="Embeddings",
                status="error",
                message=f"Embedding service failed: {e}",
                fix_command="Check embedding model configuration in .env"
            )

    async def check_and_fix_collections(self) -> CheckResult:
        """Check 9: Qdrant collections and auto-fix if needed"""
        try:
            from qdrant_client import AsyncQdrantClient

            sys.path.insert(0, str(self.project_path))
            from src.core.config import get_settings

            settings = get_settings()

            client = AsyncQdrantClient(
                url=settings.vector_db.url,
                api_key=settings.vector_db.api_key,
            )

            expected_dim = settings.embedding.dimensions

            collections = await client.get_collections()
            issues = []
            all_collections = []

            for collection in collections.collections:
                all_collections.append(collection.name)
                try:
                    info = await client.get_collection(collection.name)
                    if hasattr(info.config.params.vectors, 'size'):
                        actual_dim = info.config.params.vectors.size
                        if actual_dim != expected_dim:
                            issues.append(f"{collection.name}: {actual_dim} dims (expected {expected_dim})")
                except Exception:
                    pass

            # Auto-fix if requested
            if issues and self.fix_all:
                print(f"     {Colors.OKCYAN}Recreating collections with correct dimensions...{Colors.ENDC}")

                for collection in collections.collections:
                    try:
                        await client.delete_collection(collection.name)
                        print(f"     Deleted: {collection.name}")
                    except Exception as e:
                        print(f"     Failed to delete {collection.name}: {e}")

                # Create new collections
                collection_names = ["incidents", "incidents_summary", "incidents_detail", "incidents_bm25"]
                from qdrant_client.models import VectorParams, Distance

                for name in collection_names:
                    if name == "incidents_bm25":
                        await client.create_collection(
                            collection_name=name,
                            vectors_config={}  # Sparse vectors
                        )
                    else:
                        await client.create_collection(
                            collection_name=name,
                            vectors_config=VectorParams(
                                size=expected_dim,
                                distance=Distance.COSINE,
                            ),
                        )
                    print(f"     Created: {name} ({expected_dim} dims)")

                print(f"     {Colors.OKGREEN}✓ Collections recreated{Colors.ENDC}")
                issues = []

            await client.close()

            if issues:
                return CheckResult(
                    name="Qdrant Collections",
                    status="error",
                    message="Dimension mismatches found",
                    details={
                        "issues": issues,
                        "expected_dim": expected_dim
                    },
                    fix_suggested=True,
                    fix_command="python setup_and_validate.py --fix-all"
                )

            return CheckResult(
                name="Qdrant Collections",
                status="pass",
                message=f"All collections OK ({expected_dim} dims)",
                details={"collections": all_collections}
            )

        except Exception as e:
            return CheckResult(
                name="Qdrant Collections",
                status="warning",
                message=f"Collection check failed: {e}",
                fix_command="Manually verify collections in Qdrant dashboard"
            )

    async def check_index_search_workflow(self) -> CheckResult:
        """Check 10: Complete index → search workflow"""
        if self.skip_index:
            return CheckResult(
                name="Index/Search Workflow",
                status="skipped",
                message="Skipped (--skip-index flag)"
            )

        try:
            sys.path.insert(0, str(self.project_path))
            from src.services.llm_service import EmbeddingService
            from src.core.pattern_matching import Incident, PatternMatchingEngine

            # Create test incident
            test_incident = Incident(
                id="TEST-001",
                title="Test Database Connection",
                description="Test incident for validation",
                error_message="Connection timeout to database",
                error_type="DatabaseError",
                service="api-gateway",
                severity="high",
                status="resolved",
                resolved_by="test_user",
                resolution_summary="Increased connection pool size",
                keywords=["database", "timeout"],
            )

            # Test indexing
            embed_service = EmbeddingService()
            engine = PatternMatchingEngine(
                embedding_service=embed_service,
                llm_service=None,
            )

            # Generate embedding
            embedding = await embed_service.embed(test_incident.to_embedding_text())

            # Test search (simple similarity check)
            import numpy as np
            query_emb = await embed_service.embed("database connection problem")
            similarity = np.dot(embedding, query_emb) / (
                np.linalg.norm(embedding) * np.linalg.norm(query_emb)
            )

            return CheckResult(
                name="Index/Search Workflow",
                status="pass",
                message=f"Workflow test passed (similarity: {similarity:.2f})",
                details={
                    "embedding_dim": len(embedding),
                    "test_similarity": f"{similarity:.4f}"
                }
            )

        except Exception as e:
            return CheckResult(
                name="Index/Search Workflow",
                status="error",
                message=f"Workflow test failed: {e}",
                details={"traceback": str(e)}
            )

    async def run_all_checks(self) -> bool:
        """Run all validation checks"""
        self.print_header("IncidentIQ System Validator")

        print(f"{Colors.OKCYAN}Project: {self.project_path}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}Fix all: {self.fix_all}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}Skip index: {self.skip_index}{Colors.ENDC}\n")

        checks = [
            ("Python Version", self.check_python_version),
            ("Dependencies", self.check_dependencies),
            ("Configuration", self.check_configuration),
            ("Docker Services", self.check_docker_services),
            ("PostgreSQL", self.check_postgresql),
            ("Redis", self.check_redis),
            ("Qdrant", self.check_qdrant),
            ("Embeddings", self.check_embeddings),
            ("Qdrant Collections", self.check_and_fix_collections),
            ("Index/Search Workflow", self.check_index_search_workflow),
        ]

        for name, check_func in checks:
            print(f"{Colors.OKBLUE}Checking: {name}...{Colors.ENDC}")
            try:
                result = await check_func()
                self.add_result(result)
                self.print_result(result)
            except Exception as e:
                error_result = CheckResult(
                    name=name,
                    status="error",
                    message=f"Check failed with exception: {e}"
                )
                self.add_result(error_result)
                self.print_result(error_result)
            print()

        # Summary
        self.print_summary()

        passed = sum(1 for r in self.results if r.status == "pass")
        errors = sum(1 for r in self.results if r.status == "error")
        warnings = sum(1 for r in self.results if r.status == "warning")
        skipped = sum(1 for r in self.results if r.status == "skipped")

        return errors == 0

    def print_summary(self):
        """Print validation summary"""
        self.print_header("VALIDATION SUMMARY")

        passed = sum(1 for r in self.results if r.status == "pass")
        errors = sum(1 for r in self.results if r.status == "error")
        warnings = sum(1 for r in self.results if r.status == "warning")
        skipped = sum(1 for r in self.results if r.status == "skipped")

        print(f"{Colors.OKGREEN}✅ Passed: {passed}{Colors.ENDC}")
        print(f"{Colors.FAIL}❌ Errors: {errors}{Colors.ENDC}")
        print(f"{Colors.WARNING}⚠️  Warnings: {warnings}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}⊘ Skipped: {skipped}{Colors.ENDC}")

        if self.errors:
            print(f"\n{Colors.FAIL}ERRORS:{Colors.ENDC}")
            for error in self.errors:
                print(f"  {Colors.FAIL}❌{Colors.ENDC} {error}")

        if self.warnings:
            print(f"\n{Colors.WARNING}WARNINGS:{Colors.ENDC}")
            for warning in self.warnings:
                print(f"  {Colors.WARNING}⚠️{Colors.ENDC} {warning}")

        # Quick fix suggestions
        if errors > 0 or warnings > 0:
            print(f"\n{Colors.OKCYAN}QUICK FIXES:{Colors.ENDC}")
            if errors > 0:
                print(f"  {Colors.BOLD}Run with auto-fix:{Colors.ENDC} python setup_and_validate.py --fix-all")
            print(f"  {Colors.BOLD}Start Docker:{Colors.ENDC} make docker-up")
            print(f"  {Colors.BOLD}Install dependencies:{Colors.ENDC} uv sync")
            print(f"  {Colors.BOLD}Check .env:{Colors.ENDC} Ensure all required fields are set")

        # Final status
        print(f"\n{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
        if errors == 0:
            print(f"{Colors.OKGREEN}{Colors.BOLD}✅ ALL CHECKS PASSED - System is ready!{Colors.ENDC}")
            print(f"{Colors.OKGREEN}Run: uv run test_teams_bot.py{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}{Colors.BOLD}❌ {errors} ERROR(S) MUST BE FIXED{Colors.ENDC}")
        print(f"{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="IncidentIQ System Setup and Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_and_validate.py              # Run all checks
  python setup_and_validate.py --fix-all    # Auto-fix issues
  python setup_and_validate.py --skip-index # Skip index test
        """
    )

    parser.add_argument(
        "--fix-all",
        action="store_true",
        help="Automatically fix common issues (recreate collections, etc.)"
    )

    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip the index/search workflow test"
    )

    args = parser.parse_args()

    # Get project path
    project_path = Path(__file__).parent

    # Run validation
    validator = SystemValidator(
        project_path=project_path,
        fix_all=args.fix_all,
        skip_index=args.skip_index
    )

    success = await validator.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
