import asyncio
import random
import logging

logger = logging.getLogger(__name__)

class RetryEngine:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def sleep_for_retry(self, attempt: int, retry_after: float = None):
        """
        Sleeps for an appropriate amount of time based on the attempt number or Retry-After header.
        Uses exponential backoff with jitter.
        """
        if retry_after is not None and retry_after > 0:
            delay = min(retry_after, self.max_delay)
        else:
            delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
            delay = min(delay, self.max_delay)
            
        logger.debug(f"Sleeping for {delay:.2f} seconds before retry attempt {attempt + 1}")
        await asyncio.sleep(delay)

    @staticmethod
    def is_retryable_status(status_code: int) -> bool:
        """
        Returns True if the HTTP status code implies the request should be retried.
        Retry on 408 (Request Timeout), 429 (Too Many Requests), and 5xx (Server Errors).
        """
        if status_code in (408, 429):
            return True
        if 500 <= status_code < 600:
            return True
        return False
