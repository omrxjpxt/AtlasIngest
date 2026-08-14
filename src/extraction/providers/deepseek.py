import logging
from typing import TypeVar, Type
from pydantic import BaseModel
from .base import BaseProvider, ProviderError, RateLimitError, PayloadTooLargeError
from src.extraction.prompts import ANTI_HALLUCINATION_PROMPT
from src.config.settings import get_settings

try:
    import openai
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class DeepSeekProvider(BaseProvider):
    provider_name = "deepseek"

    def __init__(self):
        if not HAS_OPENAI:
            raise ImportError("openai is not installed")
        settings = get_settings()
        self.api_key = settings.DEEPSEEK_API_KEY
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.deepseek.com/v1")
        else:
            self.client = None
        self.model_name = "deepseek-chat" 

    async def extract_structured(self, text: str, schema: Type[T], context: str = "") -> T:
        if not self.client:
            raise ProviderError("DEEPSEEK_API_KEY is not configured", is_retryable=False)
            
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
            
        except openai.RateLimitError as e:
            raise RateLimitError(str(e))
        except openai.BadRequestError as e:
            if "context length" in str(e).lower() or "too large" in str(e).lower():
                raise PayloadTooLargeError(str(e))
            raise ProviderError(str(e), status_code=400, is_retryable=False)
        except (openai.InternalServerError, openai.APIConnectionError) as e:
            raise ProviderError(str(e), status_code=500, is_retryable=True)
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(str(e), is_retryable=False)
