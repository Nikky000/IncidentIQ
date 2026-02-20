"""
IncidentIQ FastAPI Application

REST API for:
1. Incident search and pattern matching
2. Incident indexing
3. Health checks
4. Webhook endpoints for integrations
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.pattern_matching import (
    Incident,
    IncidentMatch,
    MatchConfidence,
    get_pattern_engine,
)


# ============================================
# LIFESPAN (Startup/Shutdown)
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting IncidentIQ ({settings.app_env})")
    
    # Initialize pattern engine
    engine = await get_pattern_engine()
    print("✅ Pattern matching engine initialized")
    
    yield
    
    # Shutdown
    print("👋 Shutting down IncidentIQ")


# ============================================
# APP INITIALIZATION
# ============================================

settings = get_settings()

app = FastAPI(
    title="IncidentIQ API",
    description="AI-powered incident resolution assistant with semantic pattern matching",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# SCHEMAS
# ============================================

class IncidentSearchRequest(BaseModel):
    """Request to search for similar incidents"""
    query: str = Field(..., description="Error message or incident description")
    service: Optional[str] = Field(None, description="Filter by service name")
    limit: int = Field(5, ge=1, le=20, description="Maximum results")
    use_llm_enhancement: bool = Field(
        False, 
        description="Use LLM to enhance query understanding (more accurate but slower)"
    )


class IncidentSearchResponse(BaseModel):
    """Response with matched incidents"""
    query: str
    total_matches: int
    exact_matches: int
    partial_matches: int
    matches: list[dict]


class IncidentCreateRequest(BaseModel):
    """Request to index a new incident"""
    id: str
    title: str
    description: str
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_by_contact: Optional[str] = None
    resolution_summary: Optional[str] = None
    resolution_commands: Optional[list[str]] = None
    resolution_time_minutes: Optional[int] = None
    rca_document_url: Optional[str] = None
    runbook_url: Optional[str] = None
    conversation_url: Optional[str] = None
    channel_id: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    environment: str


# ============================================
# ENDPOINTS
# ============================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.app_env,
    )


@app.post("/api/v1/search", response_model=IncidentSearchResponse, tags=["Incidents"])
async def search_incidents(request: IncidentSearchRequest):
    """
    Search for similar incidents using semantic pattern matching.
    
    Returns incidents with confidence levels:
    - EXACT: >= 92% similarity - High confidence match
    - PARTIAL: 70-92% - Reference only, not definitive
    - NONE: < 70% - No confident match
    """
    engine = await get_pattern_engine()
    
    if request.use_llm_enhancement:
        matches = await engine.search_with_llm_enhancement(request.query)
    else:
        matches = await engine.find_similar_incidents(
            query=request.query,
            service=request.service,
            limit=request.limit,
        )
    
    exact_count = sum(1 for m in matches if m.confidence == MatchConfidence.EXACT)
    partial_count = sum(1 for m in matches if m.confidence == MatchConfidence.PARTIAL)
    
    return IncidentSearchResponse(
        query=request.query,
        total_matches=len(matches),
        exact_matches=exact_count,
        partial_matches=partial_count,
        matches=[
            {
                "incident_id": m.incident_id,
                "title": m.title,
                "similarity_score": m.similarity_score,
                "confidence": m.confidence.value,
                "resolved_by": m.resolved_by,
                "resolution_summary": m.resolution_summary,
                "resolution_commands": m.resolution_commands,
                "resolution_time_minutes": m.resolution_time_minutes,
                "rca_document_url": m.rca_document_url,
                "runbook_url": m.runbook_url,
                "original_conversation_url": m.original_conversation_url,
                "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
                "service": m.service,
                "error_type": m.error_type,
                "match_reasons": m.match_reasons,
            }
            for m in matches
        ],
    )


@app.post("/api/v1/incidents", tags=["Incidents"])
async def create_incident(request: IncidentCreateRequest):
    """
    Index a new incident for pattern matching.

    Call this when:
    - An incident is resolved
    - RCA is added
    - Resolution is confirmed working

    Uses the enhanced 4-stage hybrid pipeline for maximum accuracy.
    """
    from src.core.pattern_matching_v2 import (
        get_enhanced_pattern_engine,
        EnhancedIncident,
    )

    engine = await get_enhanced_pattern_engine()

    incident = EnhancedIncident(
        id=request.id,
        title=request.title,
        description=request.description,
        error_message=request.error_message,
        error_type=request.error_type,
        service=request.service,
        severity=request.severity,
        status="resolved",
        resolved_by=request.resolved_by,
        resolved_by_contact=request.resolved_by_contact,
        resolution_summary=request.resolution_summary,
        resolution_commands=request.resolution_commands,
        resolution_time_minutes=request.resolution_time_minutes,
        rca_document_url=request.rca_document_url,
        runbook_url=request.runbook_url,
        conversation_url=request.conversation_url,
        channel_id=request.channel_id,
        keywords=request.keywords,
        symptoms=request.symptoms,
    )

    incident_id = await engine.index_incident(incident)

    return {"status": "indexed", "incident_id": incident_id}


@app.get("/api/v1/stats", tags=["System"])
async def get_stats():
    """Get system statistics"""
    from src.core.pattern_matching_v2 import get_enhanced_pattern_engine

    engine = await get_enhanced_pattern_engine()

    # Get performance metrics from the 4-stage pipeline
    pipeline_metrics = await engine.get_metrics()

    return {
        "total_incidents": 0,  # TODO: Get from Qdrant
        "total_searches_today": 0,  # TODO: Track in Redis
        "avg_response_time_ms": pipeline_metrics.get("avg_latency_ms", 0),
        "cache_hit_rate": 0,  # TODO: Get from cache service
        "exact_match_rate": pipeline_metrics.get("exact_match_rate", 0),
        "pipeline_stages": pipeline_metrics.get("pipeline_stages", 1),
        "improvement_over_baseline": pipeline_metrics.get("improvement_over_baseline", "0%"),
    }


@app.get("/api/v1/pipeline/metrics", tags=["System"])
async def get_pipeline_metrics():
    """
    Get detailed 4-stage pipeline metrics.

    Returns performance data for marketing and monitoring:
    - Stage-wise latency breakdown
    - Candidate reduction rates
    - Accuracy improvements

    Use these metrics to back up marketing claims like:
    - "85% exact match rate"
    - "330ms average latency"
    - "40% improvement over baseline"
    """
    from src.core.pattern_matching_v2 import get_enhanced_pattern_engine

    engine = await get_enhanced_pattern_engine()

    return await engine.get_metrics()


# ============================================
# MAIN
# ============================================

def main():
    """Run the FastAPI server"""
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
