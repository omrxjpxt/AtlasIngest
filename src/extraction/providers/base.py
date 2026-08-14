import abc
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, status_code: int = 500, is_retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = is_retryable

class PayloadTooLargeError(ProviderError):
    def __init__(self, message="Payload too large"):
        super().__init__(message, status_code=413, is_retryable=False) # Handled by payload halving, not simple retry

class RateLimitError(ProviderError):
    def __init__(self, message="Rate limit exceeded", retry_after: float = None):
        super().__init__(message, status_code=429, is_retryable=True)
        self.retry_after = retry_after

class BaseProvider(abc.ABC):
    provider_name: str
    
    @abc.abstractmethod
    async def extract_structured(self, text: str, schema: Type[T], context: str = "") -> T:
        """
        Extract structured data matching the schema from the text.
        Must raise ProviderError (or specific subclasses) on failures.
        """
        pass
