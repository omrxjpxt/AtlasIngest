import asyncio
import json
import logging
from typing import AsyncGenerator, Tuple, Any, Dict, Set
from bs4 import BeautifulSoup
from pydantic import HttpUrl
from urllib.parse import urlparse
import aiohttp

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.database.models import Product, Startup
from src.database.connection import get_session
from src.models.schemas import ProductRecord, PricingModel, ProductContent, Source
from sqlalchemy import select

logger = logging.getLogger(__name__)

class AifoxxProductAdapter:
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.data_url = "https://raw.githubusercontent.com/withkarann/aifoxx/main/src/data/tools.json"
        self.startup_names: Set[str] = set()
        
    async def _load_startups(self):
        async with get_session() as session:
            result = await session.execute(select(Startup.entity_name))
            self.startup_names = {row[0].lower().strip() for row in result.all()}

    async def _extract_provider_from_html(self, html: str, url: str) -> str | None:
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Check JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                # Handle both list of graphs and single graph
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') in ('Organization', 'Corporation'):
                            if name := item.get('name'):
                                return name
                        if isinstance(item, dict) and item.get('@type') == 'WebSite':
                            if publisher := item.get('publisher'):
                                if isinstance(publisher, dict) and publisher.get('name'):
                                    return publisher['name']
                elif isinstance(data, dict):
                    # Check organization directly
                    if data.get('@type') in ('Organization', 'Corporation'):
                        if name := data.get('name'):
                            return name
                    # Check publisher
                    if publisher := data.get('publisher'):
                        if isinstance(publisher, dict) and publisher.get('name'):
                            return publisher['name']
                    # Check graph
                    if '@graph' in data:
                        for item in data['@graph']:
                            if isinstance(item, dict) and item.get('@type') in ('Organization', 'Corporation'):
                                if name := item.get('name'):
                                    return name
            except Exception:
                continue
                
        # 2. Check meta tags
        og_site_name = soup.find('meta', property='og:site_name')
        if og_site_name and og_site_name.get('content'):
            return og_site_name.get('content')
            
        return None

    def _normalize_pricing(self, pricing_str: str) -> PricingModel | None:
        if not pricing_str:
            return None
            
        p = pricing_str.lower().strip()
        if p == 'free':
            return PricingModel.FREE
        elif p == 'freemium':
            return PricingModel.FREEMIUM
        elif p == 'paid':
            return PricingModel.PAID
        elif p == 'open source':
            # Open Source -> FREE ONLY IF EXPLICIT. But AIFOXX "Open Source" tag is just open source.
            # We reject it as per strict rule unless it says free, but aifoxx just gives "Open Source"
            return None
            
        return None

    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[Tuple[ProductRecord, str], None]:
        await self._load_startups()
        
        # Fetch the JSON dataset directly
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.data_url) as response:
                    response.raise_for_status()
                    tools = await response.json(content_type=None)
            except Exception as e:
                logger.error(f"Failed to fetch AIFOXX dataset: {e}")
                return

        logger.info(f"Loaded {len(tools)} tools from AIFOXX dataset.")
        
        # Queue for fetching HTML for provider extraction
        sem = asyncio.Semaphore(20)
        
        async def process_tool(tool: dict) -> Tuple[ProductRecord, str] | None:
            name = tool.get('name', '').strip()
            url = tool.get('url', '').strip()
            pricing_raw = tool.get('pricing', '')
            
            if not name or not url:
                return None
                
            pricing = self._normalize_pricing(pricing_raw)
            if not pricing:
                return None # PRICING_UNRESOLVED
                
            # Try to resolve provider
            provider = None
            
            # 1. Exact match with YC startup names
            # Many product names match the startup name
            if name.lower() in self.startup_names:
                provider = name
                
            # Also try domain name
            try:
                domain = urlparse(url).netloc.replace('www.', '').split('.')[0]
                if domain.lower() in self.startup_names:
                    provider = next((s for s in self.startup_names if s.lower() == domain.lower()), None)
            except:
                pass
                
            # If not found, fetch official page with semaphore
            if not provider:
                async with sem:
                    try:
                        req = CrawlRequest(url=url)
                        result = await self.engine.process_request(req)
                        if result.raw_html:
                            provider = await self._extract_provider_from_html(result.raw_html, url)
                    except Exception as e:
                        logger.debug(f"Failed to fetch official page {url}: {e}")
                        
            if not provider:
                # Still unresolved
                return None
                
            try:
                record = ProductRecord(
                    source=Source(
                        name="AIFOXX",
                        url=HttpUrl(url)
                    ),
                    content=ProductContent(
                        startupName=provider,
                        pricingModel=pricing
                    )
                )
                return record, name
            except Exception as e:
                logger.debug(f"Validation failed for {name}: {e}")
                return None

        # Execute concurrent parsing
        tasks = [asyncio.create_task(process_tool(tool)) for tool in tools]
        
        completed = 0
        for task in asyncio.as_completed(tasks):
            result = await task
            if result:
                yield result
                completed += 1
                if completed >= target_count:
                    break
