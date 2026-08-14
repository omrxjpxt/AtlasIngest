import logging
from typing import TypeVar, Type
from pydantic import BaseModel
from .base import BaseProvider, ProviderError, RateLimitError, PayloadTooLargeError
from src.extraction.prompts import ANTI_HALLUCINATION_PROMPT
from src.config.settings import get_settings

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    from google.api_core.exceptions import ResourceExhausted, InvalidArgument, InternalServerError, ServiceUnavailable
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class GeminiProvider(BaseProvider):
    provider_name = "gemini"

    def __init__(self):
        if not HAS_GEMINI:
            raise ImportError("google-generativeai is not installed")
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = "gemini-1.5-flash"

    async def extract_structured(self, text: str, schema: Type[T], context: str = "") -> T:
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured", is_retryable=False)
            
        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=ANTI_HALLUCINATION_PROMPT + "\n" + context
        )
        
        config = GenerationConfig(
            response_mime_type="application/json"
        )
        
        prompt = f"Extract the required information into JSON format. Ensure all schema requirements are met.\n\nSOURCE TEXT:\n{text}"
        
        try:
            response = await model.generate_content_async(prompt, generation_config=config)
            
            # Pydantic validation handles structured errors
            return schema.model_validate_json(response.text)
            
        except ResourceExhausted as e:
            raise RateLimitError(str(e))
        except InvalidArgument as e:
            if "too large" in str(e).lower() or "exceeds" in str(e).lower():
                raise PayloadTooLargeError(str(e))
            raise ProviderError(str(e), status_code=400, is_retryable=False)
        except (InternalServerError, ServiceUnavailable) as e:
            raise ProviderError(str(e), status_code=500, is_retryable=True)
        except Exception as e:
            # Re-raise standard exceptions (like Pydantic ValidationError) to be caught by the engine
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(str(e), is_retryable=False)
