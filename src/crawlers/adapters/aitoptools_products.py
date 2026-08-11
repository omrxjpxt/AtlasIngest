import asyncio
import logging
from bs4 import BeautifulSoup
from typing import AsyncGenerator, Tuple, Optional
import re

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.database.models import Product, Startup
from src.database.connection import get_session
from sqlalchemy import select
from src.models.schemas import ProductRecord, PricingModel, ProductContent, Source

logger = logging.getLogger(__name__)

class AITopToolsAdapter:
    BASE_URL = "https://aitoptools.com"
    
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.startup_names = set()
        
    async def _load_startups(self):
        async with get_session() as session:
            result = await session.execute(select(Startup.entity_name))
            self.startup_names = {row[0].lower().strip() for row in result.all()}

    def _normalize_pricing(self, pricing_str: str) -> PricingModel | None:
        if not pricing_str:
            return None
        p = pricing_str.lower().strip()
        if 'free trial' in p:
            return None
        if p == 'free': return PricingModel.FREE
        elif p == 'freemium': return PricingModel.FREEMIUM
        elif p == 'paid': return PricingModel.PAID
        elif p == 'enterprise': return PricingModel.ENTERPRISE
        return None

    def _extract_provider(self, html: str, name: str) -> str | None:
        if name.lower() in self.startup_names:
            return name
        
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ')
        
        match = re.search(r'(?i)(?:created by|developed by|from)\s+([A-Z][a-zA-Z0-9\s\&]+?)(?=\.|,|<)', text)
        if match:
            return match.group(1).strip()
            
        match2 = re.search(r'([A-Z][a-zA-Z0-9\&]+)[\'’]s', text)
        if match2:
            return match2.group(1).strip()
            
        return name

    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[Tuple[ProductRecord | None, str], None]:
        await self._load_startups()
        
        url = "https://aitoptools.com/tool-sitemap.xml"
        req = CrawlRequest(url=url)
        res = await self.engine.process_request(req)
        if not res.raw_html:
            logger.error(f"Failed to fetch {url}")
            return
            
        import re
        tool_links = re.findall(r'<loc>(https://aitoptools.com/tool/[^<]+)</loc>', res.raw_html)
        tool_links = list(set(tool_links))
        logger.info(f"Sitemap: found {len(tool_links)} tool links.")
        
        yielded_count = 0
        batch_size = 50
        
        for i in range(0, len(tool_links), batch_size):
            batch = tool_links[i:i+batch_size]
            tasks = [self._process_tool(u) for u in batch]
            
            for task in asyncio.as_completed(tasks):
                record_tuple = await task
                if record_tuple:
                    yield record_tuple
                    yielded_count += 1
                    if yielded_count >= target_count:
                        return

    async def _process_tool(self, url: str) -> Tuple[ProductRecord | None, str] | None:
        try:
            req = CrawlRequest(url=url)
            res = await self.engine.process_request(req)
            if not res.raw_html:
                return None
                
            soup = BeautifulSoup(res.raw_html, 'html.parser')
            
            # Name
            title_tag = soup.find('h1')
            if not title_tag:
                title_tag = soup.title
            if not title_tag:
                return None
                
            name = title_tag.text.replace("Reviews 2026", "").replace("Details, Pricing, & Features", "").strip()
            name = name.split(" - ")[0].split("|")[0].strip()
            
            # Pricing
            pricing_tag = soup.find('div', class_='payment-term')
            pricing_raw = pricing_tag.text.strip() if pricing_tag else ""
            pricing = self._normalize_pricing(pricing_raw)
            
            if not pricing:
                return None
                
            # Provider
            provider = self._extract_provider(res.raw_html, name)
            if not provider:
                return None
                
            # Description
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            desc = desc_tag['content'] if desc_tag else ""
            
            # Official URL
            official_url = url
            for a in soup.find_all('a', href=True):
                if '?ref=aitoptools' in a['href']:
                    official_url = a['href'].split('?')[0]
                    break
                    
            record = ProductRecord(
                source=Source(
                    name="AITopTools",
                    url=url
                ),
                content=ProductContent(
                    startupName=provider,
                    pricingModel=pricing
                )
            )
            
            return record, name
            
        except Exception as e:
            logger.error(f"Error parsing AITopTools {url}: {e}")
            return None
