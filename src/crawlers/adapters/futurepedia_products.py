import logging
import re
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from bs4 import BeautifulSoup
import json

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.models.schemas import ProductRecord, ProductContent, Source, PricingModel

logger = logging.getLogger(__name__)

class FuturepediaProductAdapter:
    """
    Adapter for discovering and parsing AI products from Futurepedia.
    """
    BASE_URL = "https://www.futurepedia.io"
    
    # Pricing normalization mapping
    PRICING_MAP = {
        "free + paid": PricingModel.FREEMIUM,
        "freemium": PricingModel.FREEMIUM,
        "free": PricingModel.FREE,
        "subscription": PricingModel.PAID,
        "one-time purchase": PricingModel.PAID,
        "paid": PricingModel.PAID,
        "enterprise": PricingModel.ENTERPRISE
    }
    
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        
    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[tuple[ProductRecord, Optional[str]], None]:
        """
        Discovers and yields (valid ProductRecord, product_name).
        """
        yielded_count = 0
        discovered_urls = set()
        
        # We start by fetching categories
        categories = await self._fetch_categories()
        logger.info(f"Discovered {len(categories)} Futurepedia categories")
        
        for category_url in categories:
            if yielded_count >= target_count:
                break
                
            tool_urls = await self._fetch_tool_urls_from_category(category_url)
            
            # For each tool URL, fetch and parse
            for tool_url in tool_urls:
                if yielded_count >= target_count:
                    break
                    
                if tool_url in discovered_urls:
                    continue
                discovered_urls.add(tool_url)
                
                record, product_name, reject_reason = await self._fetch_and_parse_tool(tool_url)
                
                if record:
                    yield record, product_name
                    yielded_count += 1
                else:
                    logger.debug(f"Rejected product {tool_url}: {reject_reason}")
                    
    async def _fetch_categories(self) -> list[str]:
        """Fetches a list of category URLs."""
        req = CrawlRequest(url=f"{self.BASE_URL}/ai-tools")
        res = await self.engine.process_request(req)
        
        if not res.success or not res.raw_html:
            return []
            
        urls = set()
        # Find hrefs like /ai-tools/category-name or https://www.futurepedia.io/ai-tools/category-name
        matches = re.finditer(r'href="(?:https?://[^/]+)?(/ai-tools/[a-z0-9-]+)"', res.raw_html)
        for match in matches:
            url = f"{self.BASE_URL}{match.group(1)}"
            # Don't add the root page
            if url != f"{self.BASE_URL}/ai-tools":
                urls.add(url)
                
        return list(urls)
        
    async def _fetch_tool_urls_from_category(self, category_url: str) -> list[str]:
        """Fetches a list of tool URLs from a given category URL."""
        req = CrawlRequest(url=category_url)
        res = await self.engine.process_request(req)
        
        if not res.success or not res.raw_html:
            return []
            
        urls = set()
        # Find hrefs like /tool/tool-name or https://www.futurepedia.io/tool/tool-name
        matches = re.finditer(r'href="(?:https?://[^/]+)?(/tool/[a-z0-9A-Z_-]+)"', res.raw_html)
        for match in matches:
            urls.add(f"{self.BASE_URL}{match.group(1)}")
            
        return list(urls)
        
    async def _fetch_and_parse_tool(self, tool_url: str) -> tuple[Optional[ProductRecord], Optional[str], Optional[str]]:
        """Fetches a tool page and parses it. Returns (Record, product_name, RejectReason)."""
        req = CrawlRequest(url=tool_url)
        res = await self.engine.process_request(req)
        
        if not res.success or not res.raw_html:
            return None, None, "FETCH_FAILED"
            
        return self._parse_tool_html(res.raw_html, tool_url)
        
    def _parse_tool_html(self, html: str, source_url: str) -> tuple[Optional[ProductRecord], Optional[str], Optional[str]]:
        """Parses the HTML of a tool page."""
        # We can use BeautifulSoup or Regex
        soup = BeautifulSoup(html, 'html.parser')
        
        # Product Name
        # Check JSON-LD first for robust product name extraction
        product_name = None
        provider = None
        
        json_lds = soup.find_all('script', type='application/ld+json')
        for json_ld in json_lds:
            try:
                data = json.loads(json_ld.string)
                if data.get('@type') == 'SoftwareApplication':
                    product_name = data.get('name')
                    author = data.get('author', {})
                    if author.get('@type') in ('Organization', 'Person'):
                        provider = author.get('name')
            except:
                pass
                
        # Fallback to HTML extraction
        if not product_name:
            # Look for h1
            h1 = soup.find('h1')
            if h1:
                product_name = h1.get_text(strip=True)
                
        if not product_name:
            return None, None, "MISSING_PRODUCT_NAME"
            
        # Pricing extraction
        pricing_model = None
        # Try to find "Pricing:" or "Pricing Model:"
        pricing_pattern = re.search(r'Pricing Model:\s*</span>\s*<div[^>]*>([^<]+)</div>', html, re.IGNORECASE)
        if pricing_pattern:
            pricing_text = pricing_pattern.group(1).strip()
            pricing_model = self._normalize_pricing(pricing_text)
            
        if not pricing_model:
            # Look for "Free", "Freemium", "Paid" etc in the page
            # Futurepedia might have standard tags.
            # Example: <div>Freemium</div> near pricing
            pricing_matches = re.findall(r'<div[^>]*>(Free|Freemium|Paid|Enterprise|Free \+ Paid|Subscription)</div>', html, re.IGNORECASE)
            for p in pricing_matches:
                pricing_model = self._normalize_pricing(p.strip())
                if pricing_model:
                    break
                    
        if not pricing_model:
            return None, None, "PRICING_UNRESOLVED"
            
        # Provider extraction if not found in JSON-LD
        if not provider:
            # Look for "Company</p>" followed by an 'a' tag
            company_p = soup.find(lambda tag: tag.name == "p" and tag.text.strip() == "Company")
            if company_p:
                ul = company_p.find_next_sibling('ul')
                if ul:
                    li = ul.find('li')
                    if li and li.a:
                        provider = li.a.get_text(strip=True)
                        
        if not provider:
            return None, None, "PRODUCT_OWNER_UNRESOLVED"
            
        record = ProductRecord(
            source=Source(
                name="Futurepedia",
                url=source_url
            ),
            content=ProductContent(
                startupName=provider,
                pricingModel=pricing_model
            )
        )
        
        # Return tuple with record and internal product_name
        return record, product_name, None
        
    def _normalize_pricing(self, raw_pricing: str) -> Optional[PricingModel]:
        raw_lower = raw_pricing.lower().strip()
        for key, value in self.PRICING_MAP.items():
            if key in raw_lower:
                return value
        return None
