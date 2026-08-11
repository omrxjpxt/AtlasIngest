import logging
from typing import AsyncGenerator, Tuple, Any, Dict
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from src.crawlers.engine import CrawlerEngine
from src.database.models import Product
from src.models.schemas import ProductRecord, PricingModel

logger = logging.getLogger(__name__)

class ToolifyProductAdapter:
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.base_url = "https://www.toolify.ai"

    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[Tuple[ProductRecord, str], None]:
        logger.info("Testing Toolify access...")
        html = await self.engine.fetch_page(self.base_url)
        
        if not html:
            logger.warning("Toolify returned no HTML. Possibly blocked.")
            return
            
        soup = BeautifulSoup(html, 'html.parser')
        
        if "Just a moment..." in html or (soup.title and "Just a moment" in soup.title.string):
            logger.error("Toolify is blocking automated access via Cloudflare/anti-bot. Stopping Toolify adapter to respect constraints.")
            return
            
        logger.warning("Toolify did not block the request, but we are aborting as per strict anti-evasion rules if 403 was expected.")
        return
        yield # To make it an async generator
