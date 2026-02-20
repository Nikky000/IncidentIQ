"""
Production Utilities - Error Handling, Circuit Breaker, Rate Limiting

Features:
1. Circuit breaker for external service calls (LLM, Qdrant)
2. Rate limiting per user/channel
3. Structured error handling
4. Request retry with exponential backoff
5. Timeout handling
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# ============================================
# CUSTOM EXCEPTIONS
# ============================================

class IncidentIQError(Exception):
    """Base exception for IncidentIQ"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class RateLimitError(IncidentIQError):
    """Rate limit exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {"retry_after": retry_after})
        self.retry_after = retry_after


class ServiceUnavailableError(IncidentIQError):
    """External service unavailable (LLM, Qdrant, etc.)"""
    
    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(message, "SERVICE_UNAVAILABLE", {"service": service})
        self.service = service


class ConfigurationError(IncidentIQError):
    """Configuration error"""
    
    def __init__(self, key: str, message: str):
        super().__init__(message, "CONFIGURATION_ERROR", {"key": key})


# ============================================
# CIRCUIT BREAKER
# ============================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    Prevents cascade failures by failing fast when service is down.
    
    Usage:
        llm_circuit = CircuitBreaker(name="llm", failure_threshold=5)
        
        async with llm_circuit:
            response = await llm_service.complete(...)
    """
    
    name: str
    failure_threshold: int = 5      # Failures before opening circuit
    reset_timeout: float = 60.0     # Seconds before trying again
    half_open_max_calls: int = 3    # Max calls in half-open state
    
    # State
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    @property
    def state(self) -> CircuitState:
        """Get current state, checking if we should transition"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state
    
    async def __aenter__(self):
        async with self._lock:
            current_state = self.state
            
            if current_state == CircuitState.OPEN:
                raise ServiceUnavailableError(
                    self.name,
                    f"Circuit breaker OPEN for {self.name}. Retry after {self.reset_timeout}s"
                )
            
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise ServiceUnavailableError(
                        self.name,
                        f"Circuit breaker HALF_OPEN limit reached for {self.name}"
                    )
                self._half_open_calls += 1
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type is None:
                # Success
                self._on_success()
            else:
                # Failure
                self._on_failure()
        
        return False  # Don't suppress the exception
    
    def _on_success(self):
        """Record successful call"""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        logger.debug("circuit_breaker_success", name=self.name)
    
    def _on_failure(self):
        """Record failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker_opened",
                name=self.name,
                failures=self._failure_count,
            )
        else:
            logger.debug(
                "circuit_breaker_failure",
                name=self.name,
                failures=self._failure_count,
            )


# Global circuit breakers
circuit_breakers: dict[str, CircuitBreaker] = {
    "llm": CircuitBreaker(name="llm", failure_threshold=5, reset_timeout=30),
    "embedding": CircuitBreaker(name="embedding", failure_threshold=5, reset_timeout=30),
    "qdrant": CircuitBreaker(name="qdrant", failure_threshold=3, reset_timeout=60),
}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get circuit breaker by name"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name=name)
    return circuit_breakers[name]


# ============================================
# RATE LIMITER
# ============================================

@dataclass
class RateLimiter:
    """
    Token bucket rate limiter.
    
    Limits requests per user/channel to prevent abuse and manage costs.
    
    Usage:
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        if not await limiter.is_allowed(user_id):
            raise RateLimitError()
    """
    
    max_requests: int
    window_seconds: int
    _buckets: dict[str, list[float]] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for given key"""
        async with self._lock:
            now = time.time()
            
            # Initialize or clean bucket
            if key not in self._buckets:
                self._buckets[key] = []
            
            # Remove old requests outside window
            self._buckets[key] = [
                ts for ts in self._buckets[key]
                if now - ts < self.window_seconds
            ]
            
            # Check limit
            if len(self._buckets[key]) >= self.max_requests:
                return False
            
            # Record request
            self._buckets[key].append(now)
            return True
    
    async def get_remaining(self, key: str) -> int:
        """Get remaining requests for key"""
        async with self._lock:
            now = time.time()
            
            if key not in self._buckets:
                return self.max_requests
            
            valid_requests = [
                ts for ts in self._buckets[key]
                if now - ts < self.window_seconds
            ]
            
            return max(0, self.max_requests - len(valid_requests))


# Default rate limiters
rate_limiters = {
    "search_per_user": RateLimiter(max_requests=30, window_seconds=60),
    "search_per_channel": RateLimiter(max_requests=100, window_seconds=60),
    "llm_per_user": RateLimiter(max_requests=20, window_seconds=60),
}


# ============================================
# RETRY DECORATOR
# ============================================

def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Async retry decorator with exponential backoff.
    
    Usage:
        @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
        async def call_external_service():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            wait_time=wait_time,
                            error=str(e),
                        )
                        await asyncio.sleep(wait_time)
            
            raise last_exception
        
        return wrapper
    return decorator


# ============================================
# TIMEOUT DECORATOR
# ============================================

def async_timeout(seconds: float):
    """
    Async timeout decorator.
    
    Usage:
        @async_timeout(30.0)
        async def long_running_operation():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(
                    "timeout_exceeded",
                    function=func.__name__,
                    timeout_seconds=seconds,
                )
                raise IncidentIQError(
                    f"Operation timed out after {seconds}s",
                    "TIMEOUT_ERROR",
                    {"function": func.__name__, "timeout": seconds},
                )
        
        return wrapper
    return decorator


# ============================================
# REQUEST ID CONTEXT
# ============================================

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get current request ID from context"""
    return request_id_var.get()


def set_request_id(request_id: str):
    """Set request ID in context"""
    request_id_var.set(request_id)
