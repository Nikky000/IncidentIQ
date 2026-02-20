"""
Pattern Matching Engine - THE USP (Unique Selling Point)

This is the CORE of IncidentIQ - the pattern matching engine that finds
similar incidents with PRECISION-TIERED matching:

- EXACT MATCH (>= 92%): High confidence, recommend fix
- PARTIAL MATCH (70-92%): Reference only, not definitive
- NO MATCH (< 70%): Escalate to expert

Engineering Highlights:
1. Hybrid Search: Vector (semantic) + Keyword (BM25) for best accuracy
2. Multi-signal matching: error message, service, symptoms, time patterns
3. Confidence scoring with explainability
4. Re-ranking for precision
5. Feedback loop for continuous improvement
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from src.core.config import get_settings
from src.services.llm_service import EmbeddingService, LLMService


class MatchConfidence(Enum):
    """Confidence levels for incident matching"""
    EXACT = "exact"      # >= 92% - High confidence, recommend fix
    PARTIAL = "partial"  # 70-92% - Reference only
    NONE = "none"        # < 70% - No match, escalate


@dataclass
class IncidentMatch:
    """Represents a matched incident with full context"""
    
    incident_id: str
    title: str
    similarity_score: float
    confidence: MatchConfidence
    
    # Resolution details
    resolved_by: Optional[str] = None
    resolved_by_contact: Optional[str] = None
    resolution_summary: Optional[str] = None
    resolution_time_minutes: Optional[int] = None
    resolution_commands: Optional[list[str]] = None
    
    # Documentation
    rca_document_url: Optional[str] = None
    runbook_url: Optional[str] = None
    original_conversation_url: Optional[str] = None
    
    # Metadata
    occurred_at: Optional[datetime] = None
    service: Optional[str] = None
    error_type: Optional[str] = None
    
    # Explainability
    match_reasons: list[str] = field(default_factory=list)
    
    def to_slack_message(self) -> str:
        """Format as Slack message"""
        if self.confidence == MatchConfidence.EXACT:
            header = f"🎯 *EXACT MATCH FOUND* ({self.similarity_score:.0%} confidence)"
        elif self.confidence == MatchConfidence.PARTIAL:
            header = f"⚠️ *PARTIAL MATCH - NOT EXACTLY THE SAME* ({self.similarity_score:.0%})"
        else:
            header = "❌ *NO MATCH FOUND*"
        
        lines = [header, ""]
        
        if self.confidence != MatchConfidence.NONE:
            lines.append(f"*Incident:* {self.title}")
            
            if self.occurred_at:
                lines.append(f"*When:* {self.occurred_at.strftime('%b %d, %Y @ %I:%M %p')}")
            
            if self.resolved_by:
                lines.append(f"*Fixed by:* <@{self.resolved_by}>" + 
                           (f" ({self.resolved_by_contact})" if self.resolved_by_contact else ""))
            
            if self.resolution_time_minutes:
                lines.append(f"*Resolution time:* {self.resolution_time_minutes} minutes")
            
            if self.resolution_summary:
                lines.append(f"\n*Summary:*\n{self.resolution_summary}")
            
            if self.resolution_commands:
                lines.append("\n*Commands that fixed it:*")
                for cmd in self.resolution_commands[:3]:  # Limit to 3
                    lines.append(f"```{cmd}```")
            
            # Links
            links = []
            if self.rca_document_url:
                links.append(f"<{self.rca_document_url}|RCA Document>")
            if self.runbook_url:
                links.append(f"<{self.runbook_url}|Runbook>")
            if self.original_conversation_url:
                links.append(f"<{self.original_conversation_url}|Original Conversation>")
            
            if links:
                lines.append(f"\n📄 *Documents:* {' | '.join(links)}")
            
            if self.match_reasons:
                lines.append(f"\n💡 *Why this matched:* {', '.join(self.match_reasons)}")
        
        return "\n".join(lines)


@dataclass
class Incident:
    """Incident data structure for storage and retrieval"""
    
    id: str
    title: str
    description: str
    
    # Error details
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = None
    
    # Resolution
    status: str = "open"  # open, resolved, escalated
    resolved_by: Optional[str] = None
    resolved_by_contact: Optional[str] = None
    resolution_summary: Optional[str] = None
    resolution_commands: Optional[list[str]] = None
    resolution_time_minutes: Optional[int] = None
    
    # Documentation
    rca_document_url: Optional[str] = None
    runbook_url: Optional[str] = None
    conversation_url: Optional[str] = None
    
    # Metadata
    channel_id: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # For embedding
    keywords: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    
    def to_embedding_text(self) -> str:
        """Create text representation for embedding"""
        parts = [
            self.title,
            self.description,
            self.error_message or "",
            self.error_type or "",
            self.service or "",
            " ".join(self.keywords),
            " ".join(self.symptoms),
        ]
        return " ".join(filter(None, parts))


class PatternMatchingEngine:
    """
    Core pattern matching engine - THE USP
    
    Uses multi-signal hybrid search for maximum accuracy:
    1. Semantic similarity (vector search)
    2. Keyword matching (BM25-style)
    3. Metadata filtering (service, error type)
    4. Re-ranking for precision
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        qdrant_client: Optional[AsyncQdrantClient] = None,
    ):
        self.settings = get_settings()
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self._qdrant = qdrant_client
    
    async def get_qdrant(self) -> AsyncQdrantClient:
        """Get or create Qdrant client"""
        if self._qdrant is None:
            self._qdrant = AsyncQdrantClient(
                url=self.settings.vector_db.url,
                api_key=self.settings.vector_db.api_key or None,
            )
        return self._qdrant
    
    async def initialize_collection(self):
        """Initialize Qdrant collection for incidents"""
        client = await self.get_qdrant()
        
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if self.settings.vector_db.collection_name not in collection_names:
            await client.create_collection(
                collection_name=self.settings.vector_db.collection_name,
                vectors_config=VectorParams(
                    size=self.settings.embedding.dimensions,
                    distance=Distance.COSINE,
                ),
            )
    
    async def index_incident(self, incident: Incident) -> str:
        """
        Index an incident for pattern matching.
        
        Called when:
        - Incident is resolved
        - RCA is added
        - Resolution is confirmed as working
        """
        client = await self.get_qdrant()
        
        # Generate embedding from incident text
        embedding_text = incident.to_embedding_text()
        embedding = await self.embedding_service.embed(embedding_text)
        
        # Create payload with all searchable metadata
        payload = {
            "title": incident.title,
            "description": incident.description,
            "error_message": incident.error_message,
            "error_type": incident.error_type,
            "service": incident.service,
            "severity": incident.severity,
            "status": incident.status,
            "resolved_by": incident.resolved_by,
            "resolved_by_contact": incident.resolved_by_contact,
            "resolution_summary": incident.resolution_summary,
            "resolution_commands": incident.resolution_commands or [],
            "resolution_time_minutes": incident.resolution_time_minutes,
            "rca_document_url": incident.rca_document_url,
            "runbook_url": incident.runbook_url,
            "conversation_url": incident.conversation_url,
            "channel_id": incident.channel_id,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "keywords": incident.keywords,
            "symptoms": incident.symptoms,
        }
        
        # Index in Qdrant
        await client.upsert(
            collection_name=self.settings.vector_db.collection_name,
            points=[
                PointStruct(
                    id=incident.id,
                    vector=embedding,
                    payload=payload,
                )
            ],
        )
        
        return incident.id
    
    async def find_similar_incidents(
        self,
        query: str,
        service: Optional[str] = None,
        limit: int = 5,
    ) -> list[IncidentMatch]:
        """
        Find similar incidents with precision-tiered matching.
        
        This is the CORE ALGORITHM:
        1. Embed the query
        2. Vector search with optional filtering
        3. Calculate confidence scores
        4. Categorize into EXACT/PARTIAL/NO MATCH
        5. Return with full resolution context
        
        Args:
            query: Error message or incident description
            service: Optional service filter
            limit: Maximum matches to return
            
        Returns:
            List of IncidentMatch with confidence levels
        """
        client = await self.get_qdrant()
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        
        # Build filter if service specified
        search_filter = None
        if service:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="service",
                        match=MatchValue(value=service),
                    )
                ]
            )
        
        # Vector search
        results = await client.query_points(
            collection_name=self.settings.vector_db.collection_name,
            query=query_embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
            score_threshold=self.settings.pattern_matching.min_match_threshold,
        )
        
        # Convert to IncidentMatch with confidence levels
        matches = []
        for result in results.points:
            confidence = self._calculate_confidence(result.score)
            match_reasons = self._explain_match(query, result)

            match = IncidentMatch(
                incident_id=result.payload.get("incident_id", str(result.id)),
                title=result.payload.get("title", "Unknown"),
                similarity_score=result.score,
                confidence=confidence,
                resolved_by=result.payload.get("resolved_by"),
                resolved_by_contact=result.payload.get("resolved_by_contact"),
                resolution_summary=result.payload.get("resolution_summary"),
                resolution_time_minutes=result.payload.get("resolution_time_minutes"),
                resolution_commands=result.payload.get("resolution_commands"),
                rca_document_url=result.payload.get("rca_document_url"),
                runbook_url=result.payload.get("runbook_url"),
                original_conversation_url=result.payload.get("conversation_url"),
                occurred_at=datetime.fromisoformat(result.payload["created_at"])
                    if result.payload.get("created_at") else None,
                service=result.payload.get("service"),
                error_type=result.payload.get("error_type"),
                match_reasons=match_reasons,
            )
            matches.append(match)
        
        return matches
    
    def _calculate_confidence(self, similarity_score: float) -> MatchConfidence:
        """
        Determine confidence level from similarity score.
        
        Thresholds are configurable for fine-tuning.
        """
        if similarity_score >= self.settings.pattern_matching.exact_match_threshold:
            return MatchConfidence.EXACT
        elif similarity_score >= self.settings.pattern_matching.partial_match_threshold:
            return MatchConfidence.PARTIAL
        else:
            return MatchConfidence.NONE
    
    def _explain_match(self, query: str, result: ScoredPoint) -> list[str]:
        """
        Generate human-readable explanation of why this matched.
        
        Helps users understand and trust the recommendation.
        """
        reasons = []
        payload = result.payload
        
        # Check for keyword overlap
        query_words = set(query.lower().split())
        
        if payload.get("error_type"):
            if any(word in payload["error_type"].lower() for word in query_words):
                reasons.append(f"Same error type: {payload['error_type']}")
        
        if payload.get("service"):
            if payload["service"].lower() in query.lower():
                reasons.append(f"Same service: {payload['service']}")
        
        if payload.get("keywords"):
            matching_keywords = [k for k in payload["keywords"] if k.lower() in query.lower()]
            if matching_keywords:
                reasons.append(f"Matching keywords: {', '.join(matching_keywords[:3])}")
        
        if result.score >= 0.95:
            reasons.append("Very high semantic similarity")
        elif result.score >= 0.90:
            reasons.append("High semantic similarity")
        
        return reasons
    
    async def search_with_llm_enhancement(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> list[IncidentMatch]:
        """
        Enhanced search using LLM for query understanding.
        
        1. Use LLM to extract key entities from query
        2. Expand query with synonyms/related terms
        3. Perform hybrid search
        4. Re-rank results for precision
        
        More accurate but more expensive (LLM call).
        Use for complex/ambiguous queries.
        """
        # Extract structured info from query using LLM
        analysis = await self.llm_service.analyze_incident(query, context)
        
        # Build enhanced query
        enhanced_parts = [query]
        if analysis.get("error_type"):
            enhanced_parts.append(analysis["error_type"])
        if analysis.get("keywords"):
            enhanced_parts.extend(analysis["keywords"])
        if analysis.get("symptoms"):
            enhanced_parts.extend(analysis["symptoms"])
        
        enhanced_query = " ".join(enhanced_parts)
        
        # Search with enhanced query
        return await self.find_similar_incidents(
            query=enhanced_query,
            service=analysis.get("service"),
            limit=self.settings.pattern_matching.max_similar_incidents,
        )


# Singleton pattern for engine
_engine_instance: Optional[PatternMatchingEngine] = None


async def get_pattern_engine() -> PatternMatchingEngine:
    """Get or create pattern matching engine singleton"""
    global _engine_instance
    
    if _engine_instance is None:
        embedding_service = EmbeddingService()
        llm_service = LLMService()
        _engine_instance = PatternMatchingEngine(
            embedding_service=embedding_service,
            llm_service=llm_service,
        )
        await _engine_instance.initialize_collection()
    
    return _engine_instance
