"""Retry utilities with exponential backoff for external API calls."""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from packages.shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            "retry_exhausted",
                            func=func.__name__,
                            attempts=attempt + 1,
                            error=str(e),
                        )
                        raise
                    
                    logger.warning(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception  # Should never reach here
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            "retry_exhausted",
                            func=func.__name__,
                            attempts=attempt + 1,
                            error=str(e),
                        )
                        raise
                    
                    logger.warning(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception  # Should never reach here
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker_half_open", func=func.__name__)
            else:
                raise Exception(f"Circuit breaker OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("circuit_breaker_closed", func=func.__name__)
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    "circuit_breaker_opened",
                    func=func.__name__,
                    failures=self.failure_count,
                )
            raise
    
    async def call_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute async function with circuit breaker protection."""
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker_half_open", func=func.__name__)
            else:
                raise Exception(f"Circuit breaker OPEN for {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("circuit_breaker_closed", func=func.__name__)
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    "circuit_breaker_opened",
                    func=func.__name__,
                    failures=self.failure_count,
                )
            raise
