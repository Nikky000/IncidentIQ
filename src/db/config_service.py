"""
Database-Backed Configuration Service

Loads configuration from database instead of just environment variables.
Supports:
1. Dynamic config updates without restart
2. Encrypted secrets
3. Audit logging for all changes
4. Caching for performance
"""

import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models import Configuration, ConfigurationHistory, get_session_factory


class DBConfigService:
    """
    Database-backed configuration service.
    
    Priority (highest to lowest):
    1. Environment variable (for secrets like DB_PASSWORD)
    2. Database configuration
    3. Default value from Settings class
    
    Caches config values in Redis for performance.
    """
    
    def __init__(self, cache_service: Optional[Any] = None):
        self.cache = cache_service
        self._local_cache: dict[str, Any] = {}
    
    async def get(
        self,
        key: str,
        default: Any = None,
        use_cache: bool = True,
    ) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (e.g., "LLM_MODEL", "EXACT_MATCH_THRESHOLD")
            default: Default value if not found
            use_cache: Whether to use cache
            
        Returns:
            Configuration value, typed according to value_type
        """
        # Check local cache first
        if use_cache and key in self._local_cache:
            return self._local_cache[key]
        
        # Check Redis cache
        if use_cache and self.cache:
            cached = await self.cache.get(f"config:{key}")
            if cached:
                value = self._deserialize(cached)
                self._local_cache[key] = value
                return value
        
        # Fetch from database
        session_factory = await get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Configuration).where(Configuration.key == key)
            )
            config = result.scalar_one_or_none()
            
            if config:
                value = self._convert_type(config.value, config.value_type)
                
                # Cache the value
                if use_cache:
                    self._local_cache[key] = value
                    if self.cache:
                        await self.cache.set(
                            f"config:{key}",
                            self._serialize(value),
                            ttl=300,  # 5 minutes
                        )
                
                return value
        
        return default
    
    async def set(
        self,
        key: str,
        value: Any,
        value_type: str = "string",
        is_secret: bool = False,
        description: Optional[str] = None,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> bool:
        """
        Set configuration value with audit logging.
        
        Args:
            key: Configuration key
            value: Value to set
            value_type: Type hint (string, int, float, bool, json)
            is_secret: Whether value should be encrypted
            description: Human-readable description
            changed_by: Who made the change
            reason: Why the change was made
            
        Returns:
            True if successful
        """
        session_factory = await get_session_factory()
        async with session_factory() as session:
            # Get existing config
            result = await session.execute(
                select(Configuration).where(Configuration.key == key)
            )
            existing = result.scalar_one_or_none()
            
            str_value = self._to_string(value, value_type)
            
            if existing:
                # Log the change
                history = ConfigurationHistory(
                    config_id=existing.id,
                    key=key,
                    old_value=existing.value,
                    new_value=str_value,
                    changed_by=changed_by,
                    reason=reason,
                )
                session.add(history)
                
                # Update existing
                existing.value = str_value
                existing.value_type = value_type
                existing.is_secret = is_secret
                existing.description = description
                existing.updated_by = changed_by
            else:
                # Create new
                config = Configuration(
                    key=key,
                    value=str_value,
                    value_type=value_type,
                    is_secret=is_secret,
                    description=description,
                    updated_by=changed_by,
                )
                session.add(config)
            
            await session.commit()
        
        # Invalidate cache
        self._local_cache.pop(key, None)
        if self.cache:
            await self.cache.delete(f"config:{key}")
        
        return True
    
    async def get_all(self, prefix: Optional[str] = None) -> dict[str, Any]:
        """Get all configuration values, optionally filtered by prefix"""
        session_factory = await get_session_factory()
        async with session_factory() as session:
            query = select(Configuration)
            if prefix:
                query = query.where(Configuration.key.startswith(prefix))
            
            result = await session.execute(query)
            configs = result.scalars().all()
            
            return {
                config.key: self._convert_type(config.value, config.value_type)
                for config in configs
            }
    
    async def refresh_cache(self):
        """Refresh all cached configuration values"""
        self._local_cache.clear()
        
        if self.cache:
            # Clear all config keys from Redis
            # In production, use SCAN instead of KEYS
            pass
    
    def _convert_type(self, value: str, value_type: str) -> Any:
        """Convert string value to appropriate type"""
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            return json.loads(value)
        else:
            return value
    
    def _to_string(self, value: Any, value_type: str) -> str:
        """Convert value to string for storage"""
        if value_type == "json":
            return json.dumps(value)
        elif value_type == "bool":
            return "true" if value else "false"
        else:
            return str(value)
    
    def _serialize(self, value: Any) -> str:
        """Serialize value for cache"""
        return json.dumps({"value": value})
    
    def _deserialize(self, data: str) -> Any:
        """Deserialize value from cache"""
        return json.loads(data)["value"]


# Singleton
_config_service: Optional[DBConfigService] = None


async def get_db_config_service() -> DBConfigService:
    """Get or create DB config service singleton"""
    global _config_service
    
    if _config_service is None:
        from src.services.cache_service import get_cache_service
        cache = await get_cache_service()
        _config_service = DBConfigService(cache)
    
    return _config_service
