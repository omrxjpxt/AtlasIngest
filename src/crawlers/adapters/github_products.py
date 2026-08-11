import logging
import json
import asyncio
from typing import AsyncGenerator

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.models.schemas import ProductRecord, ProductContent, Source, PricingModel

logger = logging.getLogger(__name__)

class GithubProductsAdapter:
    """
    Adapter for discovering open-source AI tools/products from GitHub.
    Uses the GitHub Search API to find repositories with topic 'artificial-intelligence'.
    Pricing is deterministic (FREE) and owner is the GitHub user/org.
    """
    
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        
    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[tuple[ProductRecord, str], None]:
        yielded_count = 0
        page = 1
        
        while yielded_count < target_count:
            # Sleep to respect GitHub's 10 req/min unauthenticated search rate limit
            if page > 1:
                await asyncio.sleep(6.1)
                
            url = f"https://api.github.com/search/repositories?q=topic:artificial-intelligence+topic:tool&per_page=100&page={page}"
            req = CrawlRequest(url=url, headers={"Accept": "application/vnd.github.v3+json"})
            logger.info(f"Fetching GitHub AI products page {page}")
            
            result = await self.engine.process_request(req)
            if not result.success or not result.raw_html:
                logger.error(f"Failed to fetch GitHub products: {result.error}")
                break
                
            try:
                data = json.loads(result.raw_html)
                items = data.get("items", [])
                
                if not items:
                    break
                    
                for item in items:
                    if yielded_count >= target_count:
                        break
                        
                    repo_name = item.get("name")
                    owner = item.get("owner", {}).get("login")
                    html_url = item.get("html_url")
                    
                    if not repo_name or not owner or not html_url:
                        continue
                        
                    record = ProductRecord(
                        source=Source(
                            name="GitHub",
                            url=html_url
                        ),
                        content=ProductContent(
                            startupName=owner,
                            pricingModel=PricingModel.FREE
                        )
                    )
                    
                    yield record, repo_name
                    yielded_count += 1
                    
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from GitHub API")
                break
            except Exception as e:
                logger.error(f"Error parsing GitHub data: {e}")
                break
                
            page += 1
