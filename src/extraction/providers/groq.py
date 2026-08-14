import logging
from typing import TypeVar, Type
from pydantic import BaseModel
from .base import BaseProvider, ProviderError, RateLimitError, PayloadTooLargeError
from src.extraction.prompts import ANTI_HALLUCINATION_PROMPT
from src.config.settings import get_settings

try:
    import groq
    from groq import AsyncGroq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class GroqProvider(BaseProvider):
    provider_name = "groq"

    def __init__(self):
        if not HAS_GROQ:
            raise ImportError("groq is not installed")
        settings = get_settings()
        self.api_key = settings.GROQ_API_KEY
        if self.api_key:
            self.client = AsyncGroq(api_key=self.api_key)
        else:
            self.client = None
        self.model_name = "llama3-70b-8192" # Use a fast, capable model

    async def extract_structured(self, text: str, schema: Type[T], context: str = "") -> T:
        if not self.client:
            raise ProviderError("GROQ_API_KEY is not configured", is_retryable=False)
            
        system_prompt = ANTI_HALLUCINATION_PROMPT + "\n" + context + "\nReturn ONLY valid JSON."
        user_prompt = f"Extract the required information into JSON format. Ensure all schema requirements are met.\n\nSOURCE TEXT:\n{text}"
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model_name,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return schema.model_validate_json(content)
            
        except groq.RateLimitError as e:
            # Try to extract retry_after from headers if possible, otherwise None
            raise RateLimitError(str(e))
        except groq.BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                raise PayloadTooLargeError(str(e))
            raise ProviderError(str(e), status_code=400, is_retryable=False)
        except (groq.InternalServerError, groq.APIConnectionError) as e:
            raise ProviderError(str(e), status_code=500, is_retryable=True)
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(str(e), is_retryable=False)
