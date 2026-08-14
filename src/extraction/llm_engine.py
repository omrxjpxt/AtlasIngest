import logging
from typing import TypeVar, Type, Tuple, Optional
from pydantic import BaseModel

from .providers.chain import ProviderChain
from .cleaner import clean_html
from .chunking import get_token_count, truncate_to_max_tokens

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class LLMEngine:
    def __init__(self, max_tokens: int = 15000):
        self.chain = ProviderChain()
        self.max_tokens = max_tokens

    async def extract(self, raw_html: str, schema: Type[T], context: str = "") -> Tuple[Optional[T], dict]:
        """
        Cleans the HTML, chunks it safely, and runs the LLM extraction chain.
        Returns the parsed Pydantic object and audit metadata.
        """
        # 1. Clean HTML
        cleaned_text = clean_html(raw_html)
        
        # 2. Token counting and initial safe truncation
        token_count = get_token_count(cleaned_text)
        if token_count > self.max_tokens:
            logger.info(f"Cleaned text exceeds safe limit ({token_count} > {self.max_tokens}). Truncating.")
            cleaned_text = truncate_to_max_tokens(cleaned_text, self.max_tokens)
            
        # 3. Provider Chain Extraction
        result, audit_metadata = await self.chain.extract_with_fallback(cleaned_text, schema, context)
        
        return result, audit_metadata
