"""
IncidentIQ Configuration Module

Supports ZERO VENDOR LOCK-IN:
- Any LLM provider via LiteLLM (100+ providers)
- Custom enterprise endpoints for LLM and Embeddings
- Self-hosted or cloud vector database
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """
    LLM Configuration - Vendor Agnostic via LiteLLM
    
    Supports:
    - OpenAI: openai/gpt-4, openai/gpt-3.5-turbo
    - Anthropic: anthropic/claude-3-sonnet
    - Azure: azure/deployment-name
    - Ollama (local): ollama/llama2, ollama/mistral
    - Custom: Any endpoint compatible with OpenAI API format
    
    Enterprise customers can bring their own LLM:
    - Set LLM_MODEL to your model identifier
    - Set LLM_API_BASE to your inference endpoint
    - Set LLM_API_KEY to your API key
    """
    
    model: str = Field(
        default="anthropic/claude-3-5-sonnet-20241022",
        alias="LLM_MODEL",
        description="LiteLLM model identifier (e.g., openai/gpt-4, anthropic/claude-3-sonnet)"
    )
    api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    api_base: Optional[str] = Field(
        default=None, 
        alias="LLM_API_BASE",
        description="Custom endpoint URL for enterprise LLM inference"
    )
    
    # Fallback configuration for reliability
    fallback_model: Optional[str] = Field(default="openai/gpt-4o-mini", alias="LLM_FALLBACK_MODEL")
    fallback_api_key: Optional[str] = Field(default=None, alias="LLM_FALLBACK_API_KEY")
    
    # Performance settings
    max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")  # Low for accuracy
    timeout: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class EmbeddingSettings(BaseSettings):
    """
    Embedding Configuration - Vendor Agnostic

    Supports:
    - OpenAI: openai/text-embedding-3-small, text-embedding-3-large
    - Cohere: cohere/embed-english-v3.0
    - Azure: azure/embedding-deployment
    - Ollama (local, FREE): ollama/nomic-embed-text
    - sentence-transformers (local, FREE): all-MiniLM-L6-v2
    - Custom: Any endpoint compatible with OpenAI embeddings API

    Enterprise customers can bring their own embedding service.
    """

    model: str = Field(
        default="openai/text-embedding-3-small",
        alias="EMBEDDING_MODEL"
    )
    api_key: Optional[str] = Field(default=None, alias="EMBEDDING_API_KEY")
    api_base: Optional[str] = Field(
        default=None,
        alias="EMBEDDING_API_BASE",
        description="Custom endpoint URL for enterprise embedding service"
    )
    dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")

    # Local embeddings (FREE, no API key needed)
    use_local_embeddings: bool = Field(default=False, alias="USE_LOCAL_EMBEDDINGS")

    # Batch processing for efficiency
    batch_size: int = Field(default=100, alias="EMBEDDING_BATCH_SIZE")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class VectorDBSettings(BaseSettings):
    """Qdrant Vector Database Configuration"""
    
    url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    collection_name: str = Field(default="incidents", alias="QDRANT_COLLECTION_NAME")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class DatabaseSettings(BaseSettings):
    """PostgreSQL Configuration"""
    
    url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/incidentiq",
        alias="DATABASE_URL"
    )
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CacheSettings(BaseSettings):
    """Redis Caching Configuration"""
    
    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    ttl_seconds: int = Field(default=3600, alias="CACHE_TTL_SECONDS")
    
    # Semantic caching for LLM responses (major cost saver!)
    semantic_cache_enabled: bool = Field(default=True, alias="SEMANTIC_CACHE_ENABLED")
    semantic_cache_threshold: float = Field(
        default=0.95,
        alias="SEMANTIC_CACHE_SIMILARITY_THRESHOLD",
        description="Similarity threshold for semantic cache hits (0.95 = very similar queries)"
    )
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class PatternMatchingSettings(BaseSettings):
    """
    Pattern Matching Configuration - THE USP

    Precision-tiered matching:
    - EXACT MATCH: >= 92% similarity - recommend with high confidence
    - PARTIAL MATCH: 70-92% - show as reference, not definitive
    - NO MATCH: < 70% - don't recommend, escalate to expert

    NEW: 4-Stage Hybrid Pipeline Configuration
    """

    exact_match_threshold: float = Field(
        default=0.92,
        alias="EXACT_MATCH_THRESHOLD",
        description="Minimum similarity for EXACT MATCH (high confidence)"
    )
    partial_match_threshold: float = Field(
        default=0.70,
        alias="PARTIAL_MATCH_THRESHOLD",
        description="Minimum similarity for PARTIAL MATCH (reference only)"
    )
    min_match_threshold: float = Field(
        default=0.50,
        alias="MIN_MATCH_THRESHOLD",
        description="Below this, consider NO MATCH"
    )
    max_similar_incidents: int = Field(
        default=5,
        alias="MAX_SIMILAR_INCIDENTS"
    )

    # Hybrid search (vector + keyword for better accuracy)
    vector_weight: float = Field(default=0.7, alias="VECTOR_SEARCH_WEIGHT")
    keyword_weight: float = Field(default=0.3, alias="KEYWORD_SEARCH_WEIGHT")

    # 4-Stage Pipeline Configuration
    use_hybrid_pipeline: bool = Field(
        default=True,
        alias="USE_HYBRID_PIPELINE",
        description="Enable 4-stage hybrid retrieval pipeline (40-50% better accuracy)"
    )
    enable_bm25: bool = Field(
        default=True,
        alias="ENABLE_BM25_STAGE",
        description="Enable Stage 1: BM25 fast filter"
    )
    enable_bi_encoder: bool = Field(
        default=True,
        alias="ENABLE_BI_ENCODER_STAGE",
        description="Enable Stage 2: Bi-encoder semantic search"
    )
    enable_colbert: bool = Field(
        default=True,
        alias="ENABLE_COLBERT_STAGE",
        description="Enable Stage 3: ColBERT late interaction"
    )
    enable_cross_encoder: bool = Field(
        default=False,  # Disabled by default (requires model)
        alias="ENABLE_CROSS_ENCODER_STAGE",
        description="Enable Stage 4: Cross-encoder re-ranking"
    )

    # Pipeline weights (tunable for optimization)
    bm25_weight: float = Field(default=0.10, alias="BM25_WEIGHT")
    bi_encoder_weight: float = Field(default=0.25, alias="BI_ENCODER_WEIGHT")
    colbert_weight: float = Field(default=0.40, alias="COLBERT_WEIGHT")
    cross_encoder_weight: float = Field(default=0.25, alias="CROSS_ENCODER_WEIGHT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @field_validator("exact_match_threshold", "partial_match_threshold", "min_match_threshold")
    @classmethod
    def validate_thresholds(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        return v


class SlackSettings(BaseSettings):
    """Slack Bot Configuration"""
    
    bot_token: Optional[str] = Field(default=None, alias="SLACK_BOT_TOKEN")
    app_token: Optional[str] = Field(default=None, alias="SLACK_APP_TOKEN")
    signing_secret: Optional[str] = Field(default=None, alias="SLACK_SIGNING_SECRET")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Main Application Settings"""
    
    app_name: str = Field(default="incidentiq", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    pattern_matching: PatternMatchingSettings = Field(default_factory=PatternMatchingSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
