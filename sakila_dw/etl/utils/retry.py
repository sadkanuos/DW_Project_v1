"""Retry decorator for transient failures."""

import functools
import logging
import time
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from etl.utils.config_helpers import get_config

logger = logging.getLogger("sakila_dw")

F = TypeVar("F", bound=Callable[..., Any])


def retry(
    func: Optional[F] = None,
    *,
    max_attempts: Optional[int] = None,
    backoff_seconds: Optional[int] = None,
    exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> F:
    """
    Retry a function on transient failures with linear backoff.
    Configuration can be overridden via kwargs or sourced from global config.

    Args:
        func: The function to decorate
        max_attempts: Override max retry attempts (default from config)
        backoff_seconds: Override backoff seconds (default from config)
        exceptions: Override retryable exceptions (default from config)

    Returns:
        Decorated function with retry logic
    """
    if func is not None:
        # Called as @retry without parentheses
        return _make_retry_decorator(func, max_attempts, backoff_seconds, exceptions)  # type: ignore

    # Called as @retry(max_attempts=5, ...)
    def decorator(f: F) -> F:
        return _make_retry_decorator(f, max_attempts, backoff_seconds, exceptions)  # type: ignore

    return decorator  # type: ignore


def _resolve(override: Optional[Any], default: Any) -> Any:
    """Resolve a value, using override if provided, otherwise default."""
    return override if override is not None else default


def _make_retry_decorator(
    func: F,
    max_attempts: Optional[int],
    backoff_seconds: Optional[int],
    exceptions: Optional[Tuple[Type[Exception], ...]],
) -> F:
    """Create the actual retry wrapper function."""
    config = get_config()
    actual_max = _resolve(max_attempts, config.retry.max_attempts)
    actual_backoff = _resolve(backoff_seconds, config.retry.backoff_seconds)
    actual_exceptions = _resolve(exceptions, config.retry.retryable_exceptions)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(1, actual_max + 1):
            try:
                return func(*args, **kwargs)
            except actual_exceptions as exc:
                last_exc = exc
                if attempt == actual_max:
                    logger.error(
                        "%s failed after %d attempts: %s",
                        func.__name__,
                        actual_max,
                        exc,
                    )
                    raise
                wait = actual_backoff * attempt
                logger.warning(
                    "%s failed (attempt %d/%d): %s -- retrying in %ds",
                    func.__name__,
                    attempt,
                    actual_max,
                    exc,
                    wait,
                )
                time.sleep(wait)
        raise last_exc  # pragma: no cover - unreachable safeguard

    return wrapper  # type: ignore
