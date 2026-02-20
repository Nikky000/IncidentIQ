"""
Database Models with SQLAlchemy

Features:
1. Configuration stored in DB (not just env vars)
2. Audit logging for all changes
3. Incident storage with full metadata
4. Expert graph for who-knows-what
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models"""
    pass


# ============================================
# CONFIGURATION MODELS (DB-based config)
# ============================================

class Configuration(Base):
    """
    Database-backed configuration.
    
    Allows changing settings without redeploying:
    - LLM API keys and endpoints
    - Pattern matching thresholds
    - Feature flags
    
    Sensitive values are encrypted at rest.
    """
    __tablename__ = "configurations"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string")  # string, int, float, bool, json
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255))


class ConfigurationHistory(Base):
    """Audit log for configuration changes"""
    __tablename__ = "configuration_history"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    config_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("configurations.id"))
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reason: Mapped[Optional[str]] = mapped_column(Text)


# ============================================
# INCIDENT MODELS
# ============================================

class Incident(Base):
    """
    Incident record with full metadata.
    
    Stores:
    - Incident details and error messages
    - Resolution information
    - Links to documentation
    - Expert who resolved it
    """
    __tablename__ = "incidents"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    
    # Basic info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    severity: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    
    # Error details
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_type: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    error_stack_trace: Mapped[Optional[str]] = mapped_column(Text)
    
    # Affected system
    service: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    environment: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    
    # Resolution
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255))
    resolved_by_contact: Mapped[Optional[str]] = mapped_column(String(500))
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text)
    resolution_commands: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    resolution_time_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Documentation
    rca_document_url: Mapped[Optional[str]] = mapped_column(String(1000))
    runbook_url: Mapped[Optional[str]] = mapped_column(String(1000))
    conversation_url: Mapped[Optional[str]] = mapped_column(String(1000))
    
    # Chat context
    channel_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50))  # slack, teams, gchat
    
    # Searchable metadata
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(String(100)))
    symptoms: Mapped[Optional[list]] = mapped_column(ARRAY(String(255)))
    labels: Mapped[Optional[dict]] = mapped_column(JSONB, default={})
    
    # Vector search
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Feedback
    feedback_score: Mapped[Optional[float]] = mapped_column(Float)  # 1-5 rating
    total_matches: Mapped[int] = mapped_column(Integer, default=0)  # How often this was matched
    successful_matches: Mapped[int] = mapped_column(Integer, default=0)  # How often match was marked helpful


# ============================================
# EXPERT GRAPH MODELS
# ============================================

class Expert(Base):
    """
    Expert profile for who-knows-what.
    
    Auto-populated from incident resolutions.
    Used for expert finding at 12 AM when dev is sleeping.
    """
    __tablename__ = "experts"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Identity
    user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # slack, teams
    display_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    timezone: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Stats
    incidents_resolved: Mapped[int] = mapped_column(Integer, default=0)
    avg_resolution_time_minutes: Mapped[Optional[float]] = mapped_column(Float)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Availability (for timezone-aware expert finding)
    available_start_hour: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    available_end_hour: Mapped[Optional[int]] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpertSkill(Base):
    """
    Maps experts to their areas of expertise.
    
    Auto-generated from resolutions:
    - Service familiarity
    - Error type expertise
    - Technology skills
    """
    __tablename__ = "expert_skills"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    expert_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("experts.id"), index=True)
    
    skill_type: Mapped[str] = mapped_column(String(50), nullable=False)  # service, error_type, technology
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    proficiency_score: Mapped[float] = mapped_column(Float, default=1.0)  # Based on resolution count
    incident_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('expert_id', 'skill_type', 'skill_name', name='uq_expert_skill'),
    )


# ============================================
# SEARCH & FEEDBACK MODELS
# ============================================

class SearchLog(Base):
    """
    Log all searches for analytics and feedback loop.
    
    Used to:
    - Track what users search for
    - measure match quality
    - Identify gaps in knowledge base
    """
    __tablename__ = "search_logs"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    query: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(255))
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Results
    total_results: Mapped[int] = mapped_column(Integer, default=0)
    exact_matches: Mapped[int] = mapped_column(Integer, default=0)
    partial_matches: Mapped[int] = mapped_column(Integer, default=0)
    top_match_score: Mapped[Optional[float]] = mapped_column(Float)
    top_match_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Performance
    latency_ms: Mapped[int] = mapped_column(Integer)
    used_llm_enhancement: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Feedback
    was_helpful: Mapped[Optional[bool]] = mapped_column(Boolean)
    feedback_comment: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ============================================
# DATABASE ENGINE & SESSION
# ============================================

_engine = None
_session_factory = None


async def get_engine():
    """Get or create async database engine with connection pooling"""
    global _engine
    
    if _engine is None:
        settings = get_settings()
        
        _engine = create_async_engine(
            settings.database.url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=settings.debug,
        )
    
    return _engine


async def get_session_factory():
    """Get async session factory"""
    global _session_factory
    
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )
    
    return _session_factory


async def init_db():
    """Initialize database tables"""
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
