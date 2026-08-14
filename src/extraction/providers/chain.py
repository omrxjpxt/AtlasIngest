import logging
from typing import TypeVar, Type, List, Tuple, Optional
from pydantic import BaseModel, ValidationError

from .base import BaseProvider, ProviderError, RateLimitError, PayloadTooLargeError
from .gemini import GeminiProvider
from .groq import GroqProvider
from .deepseek import DeepSeekProvider
from src.crawlers.retry import RetryEngine
from src.extraction.chunking import halve_payload

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class ProviderChain:
    def __init__(self, max_retries_per_provider: int = 3):
        self.providers: List[BaseProvider] = []
        
        # Instantiate available providers in strict priority order
        try:
            self.providers.append(GeminiProvider())
        except Exception as e:
            logger.warning(f"Skipping Gemini provider: {e}")
            
        try:
            self.providers.append(GroqProvider())
        except Exception as e:
            logger.warning(f"Skipping Groq provider: {e}")
            
        try:
            self.providers.append(DeepSeekProvider())
        except Exception as e:
            logger.warning(f"Skipping DeepSeek provider: {e}")
            
        if not self.providers:
            logger.error("No LLM providers could be configured.")
            
        self.retry_engine = RetryEngine(max_retries=max_retries_per_provider, base_delay=2.0, max_delay=60.0)

    async def extract_with_fallback(self, text: str, schema: Type[T], context: str = "") -> Tuple[Optional[T], dict]:
        """
        Attempts to extract structured data using the provider chain.
        Returns the parsed Pydantic object and an audit metadata dictionary.
        """
        audit_metadata = {
            "fallback_occurred": False,
            "provider_used": None,
            "validation_failure_count": 0,
            "rate_limit_events": 0,
            "payload_reduction_events": 0,
            "errors": []
        }
        
        current_text = text
        
        for idx, provider in enumerate(self.providers):
            if idx > 0:
                audit_metadata["fallback_occurred"] = True
                
            provider_name = provider.provider_name
            logger.info(f"Attempting extraction with {provider_name}")
            
            for attempt in range(self.retry_engine.max_retries + 1):
                try:
                    result = await provider.extract_structured(current_text, schema, context)
                    audit_metadata["provider_used"] = provider_name
                    return result, audit_metadata
                    
                except PayloadTooLargeError as e:
                    logger.warning(f"[{provider_name}] Payload too large: {e}")
                    audit_metadata["payload_reduction_events"] += 1
                    current_text = halve_payload(current_text)
                    # Retry with halved payload immediately without sleeping
                    continue
                    
                except RateLimitError as e:
                    logger.warning(f"[{provider_name}] Rate limit hit on attempt {attempt+1}: {e}")
                    audit_metadata["rate_limit_events"] += 1
                    if attempt < self.retry_engine.max_retries:
                        await self.retry_engine.sleep_for_retry(attempt, retry_after=e.retry_after)
                        continue
                    else:
                        audit_metadata["errors"].append(f"{provider_name}: Rate limit budget exhausted.")
                        break # Move to next provider
                        
                except ValidationError as e:
                    logger.warning(f"[{provider_name}] Pydantic validation failed: {e}")
                    audit_metadata["validation_failure_count"] += 1
                    # Give it exactly one retry on validation failure by manipulating context
                    if attempt < 1: # only one validation retry allowed per provider
                        context += f"\nPrevious attempt failed schema validation: {e}. Ensure you output strict JSON matching the schema."
                        continue
                    else:
                        audit_metadata["errors"].append(f"{provider_name}: Validation failed repeatedly.")
                        break # Move to next provider
                        
                except ProviderError as e:
                    if e.is_retryable and attempt < self.retry_engine.max_retries:
                        logger.warning(f"[{provider_name}] Retryable error: {e}")
                        await self.retry_engine.sleep_for_retry(attempt)
                        continue
                    else:
                        logger.error(f"[{provider_name}] Non-retryable error or budget exhausted: {e}")
                        audit_metadata["errors"].append(f"{provider_name}: {e}")
                        break # Move to next provider
                        
                except Exception as e:
                    logger.error(f"[{provider_name}] Unexpected error: {e}")
                    audit_metadata["errors"].append(f"{provider_name}: {e}")
                    break # Move to next provider
                    
        return None, audit_metadata
