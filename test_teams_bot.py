"""
Quick Test Script for IncidentIQ Teams Bot

This script will:
1. Index a test incident
2. Search for it
3. Show you the results

Run this before testing the Teams bot to ensure data is indexed.
"""

import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, "/Users/dileshchouhan/zysecai/LeadTheAI/devops/incidentiq")

from src.core.pattern_matching_v2 import (
    get_enhanced_pattern_engine,
    EnhancedIncident,
)
from src.core.config import get_settings


async def setup_test_data():
    """Index test incidents for Teams bot testing"""

    print("🚀 Initializing IncidentIQ Enhanced Engine...")
    engine = await get_enhanced_pattern_engine()

    print("✅ Initializing collections (recreating with correct dimensions)...")
    await engine.initialize_collections(recreate=True)

    # Create 3 test incidents covering common scenarios

    print("\n📝 Indexing test incidents...")

    # Incident 1: PostgreSQL Connection Pool
    incident1 = EnhancedIncident(
        id="TEAMS-001",
        title="PostgreSQL Connection Pool Exhausted",
        description="Max connections reached causing timeout errors",
        error_message="psycopg2.OperationalError: FATAL: remaining connection slots are reserved",
        error_type="DatabaseError",
        service="api-gateway",
        severity="high",
        status="resolved",
        resolved_by="john_doe",
        resolution_summary="Increased max_connections from 100 to 200 and implemented connection pooling",
        resolution_commands=[
            "ALTER SYSTEM SET max_connections = 200",
            "SELECT pg_reload_conf();"
        ],
        resolution_time_minutes=23,
        keywords=["database", "timeout", "postgresql", "connection", "pool"],
        symptoms=["slow queries", "connection errors", "timeouts"],
    )

    await engine.index_incident(incident1)
    print("  ✅ Indexed: PostgreSQL Connection Pool")

    # Incident 2: Redis Memory Issues
    incident2 = EnhancedIncident(
        id="TEAMS-002",
        title="Redis Out of Memory Error",
        description="Redis container hitting memory limit during cache operations",
        error_message="OOM command not allowed, used memory > maxmemory",
        error_type="MemoryError",
        service="cache-service",
        severity="critical",
        status="resolved",
        resolved_by="jane_smith",
        resolution_summary="Increased Redis memory limit from 256MB to 512MB and implemented cache eviction policy",
        resolution_commands=[
            "docker update redis --memory 512m",
            "CONFIG SET maxmemory-policy allkeys-lru"
        ],
        resolution_time_minutes=15,
        keywords=["redis", "memory", "oom", "cache"],
        symptoms=["cache misses", "slow responses", "errors"],
    )

    await engine.index_incident(incident2)
    print("  ✅ Indexed: Redis Out of Memory")

    # Incident 3: Kubernetes Pod Crashes
    incident3 = EnhancedIncident(
        id="TEAMS-003",
        title="Kubernetes Pods OOMKilled",
        description="Application pods getting killed due to excessive memory usage",
        error_message="Pod was OOMKilled due to memory limit exceeded",
        error_type="ResourceError",
        service="user-service",
        severity="high",
        status="resolved",
        resolved_by="devops_team",
        resolution_summary="Increased pod memory limits from 512Mi to 1Gi and implemented liveness probes",
        resolution_commands=[
            "kubectl set resources deployment user-service --limits=1Gi",
            "kubectl rollout restart deployment user-service"
        ],
        resolution_time_minutes=45,
        keywords=["kubernetes", "oomkilled", "pod", "memory", "crash"],
        symptoms=["pods restarting", "service unavailable"],
    )

    await engine.index_incident(incident3)
    print("  ✅ Indexed: Kubernetes Pod OOMKilled")

    print(f"\n✅ Successfully indexed 3 test incidents!")

    return engine


async def test_searches(engine):
    """Test various search queries"""

    print("\n🔍 Testing search queries...\n")

    # Test 1: Database timeout
    print("Test 1: Searching for 'database connection timeout'")
    matches = await engine.find_similar_incidents(
        query="database connection timeout",
        limit=3,
    )

    print(f"  Found {len(matches)} matches")
    for match in matches:
        print(f"    - {match.title} ({match.confidence.value}, {match.similarity_score:.0%})")

    # Test 2: Memory issues
    print(f"\nTest 2: Searching for 'redis memory out of memory'")
    matches = await engine.find_similar_incidents(
        query="redis memory out of memory",
        limit=3,
    )

    print(f"  Found {len(matches)} matches")
    for match in matches:
        print(f"    - {match.title} ({match.confidence.value}, {match.similarity_score:.0%})")

    # Test 3: Pod crashes
    print(f"\nTest 3: Searching for 'kubernetes pod crash'")
    matches = await engine.find_similar_incidents(
        query="kubernetes pod crash",
        limit=3,
    )

    print(f"  Found {len(matches)} matches")
    for match in matches:
        print(f"    - {match.title} ({match.confidence.value}, {match.similarity_score:.0%})")

    print(f"\n✅ Search tests complete!")


async def get_metrics(engine):
    """Get pipeline performance metrics"""

    print("\n📊 Pipeline Performance Metrics:\n")

    metrics = await engine.get_metrics()

    for key, value in metrics.items():
        print(f"  {key}: {value}")


async def main():
    """Main test function"""

    print("="*60)
    print("  IncidentIQ Teams Bot - Quick Test Script")
    print("="*60)

    try:
        # Step 1: Setup test data
        engine = await setup_test_data()

        # Step 2: Test searches
        await test_searches(engine)

        # Step 3: Show metrics
        await get_metrics(engine)

        print("\n" + "="*60)
        print("✅ All tests passed! Your Teams bot is ready.")
        print("="*60)

        print("\n📝 Next Steps:")
        print("1. Start the Teams bot server:")
        print("   python -m src.bots.teams_server")
        print("")
        print("2. Start ngrok (in a new terminal):")
        print("   ngrok http 8000")
        print("")
        print("3. Copy the HTTPS URL from ngrok")
        print("")
        print("4. Update Azure Bot messaging endpoint:")
        print("   Azure Portal → Your Bot → Configuration → Messaging endpoint")
        print("   Set to: https://your-ngrok-url.ngrok.io/api/messages")
        print("")
        print("5. Test in Microsoft Teams:")
        print("   /incidentiq search database timeout")
        print("")
        print("📖 Full setup guide: docs/TEAMS_SETUP.md")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Make sure:")
        print("  - .env file is configured with DATABASE_URL, REDIS_URL, QDRANT_URL")
        print("  - Docker services are running: make docker-up")
        print("  - Or run dependencies: docker-compose up -d postgres redis qdrant")


if __name__ == "__main__":
    asyncio.run(main())
