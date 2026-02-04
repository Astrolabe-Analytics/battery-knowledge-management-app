"""
Retry utilities with exponential backoff for API calls.
"""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)


def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        exponential_base: Base for exponential backoff (delay *= base)
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry

    Example:
        @retry_with_exponential_backoff(max_retries=3)
        def api_call():
            return client.messages.create(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # If this was the last attempt, re-raise
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    # Log the retry
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    # Wait before retrying
                    time.sleep(delay)

                    # Exponential backoff with max delay cap
                    delay = min(delay * exponential_base, max_delay)

            # Should never reach here, but just in case
            raise last_exception

        return wrapper
    return decorator


def anthropic_api_call_with_retry(func: Callable) -> Callable:
    """
    Specialized retry decorator for Anthropic API calls.
    Handles rate limits and transient errors with appropriate backoff.
    """
    return retry_with_exponential_backoff(
        max_retries=5,
        initial_delay=2.0,
        exponential_base=2.0,
        max_delay=60.0,
        exceptions=(Exception,)  # Catch all exceptions for API calls
    )(func)
