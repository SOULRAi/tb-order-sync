"""Retry / backoff helpers built on tenacity."""

from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from utils.logger import get_logger

logger = get_logger(__name__)


def default_retry(max_attempts: int = 3):
    """Decorator: retry with exponential backoff on transient errors."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((IOError, ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, log_level=20),  # INFO
        reraise=True,
    )
