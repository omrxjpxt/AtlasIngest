import logging
import json
import re
from typing import AsyncGenerator, Dict, Any
from urllib.parse import unquote

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.models.schemas import StartupRecord, StartupContent, StartupContentData, Source

logger = logging.getLogger(__name__)

class YCStartupAdapter:
    """
    Adapter for discovering and parsing AI startups from Y Combinator's server-rendered HTML.
    Uses the embedded data-page JSON payload to extract reliable structured data.
    """
    
    BASE_URL = "https://www.ycombinator.com/companies/industry/ai"
    
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        
    def _build_request_for_page(self, page: int) -> CrawlRequest:
        """Constructs a CrawlRequest for a specific page."""
        url = f"{self.BASE_URL}?page={page}" if page > 1 else self.BASE_URL
        return CrawlRequest(url=url)
        
    async def fetch_and_parse_all(self, target_count: int) -> AsyncGenerator[StartupRecord, None]:
        """
        Yields valid StartupRecord objects. 
        Paginates until target_count is reached or source is exhausted.
        """
        page = 1
        total_pages = 1 # Will be updated after first request
        yielded_count = 0
        
        while page <= total_pages and yielded_count < target_count:
            req = self._build_request_for_page(page)
            logger.info(f"Fetching YC page {page}")
            
            result = await self.engine.process_request(req)
            if not result.success or not result.raw_html:
                logger.error(f"Failed to fetch YC page {page}: {result.error}")
                break
                
            try:
                # Extract the data-page attribute
                match = re.search(r'data-page="([^"]+)"', result.raw_html)
                if not match:
                    logger.error(f"Failed to find data-page attribute on YC page {page}")
                    break
                    
                payload = match.group(1).replace('&quot;', '"')
                data = json.loads(payload)
                
                props = data.get("props", {})
                total_pages = props.get("totalPages", total_pages)
                companies = props.get("companies", [])
                
                if not companies:
                    break
                    
                for company in companies:
                    if yielded_count >= target_count:
                        break
                        
                    record = self._parse_company(company)
                    if record:
                        yield record
                        yielded_count += 1
                        
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from YC page {page}")
                break
            except Exception as e:
                logger.error(f"Error parsing YC page {page}: {e}")
                break
                
            page += 1
            
    def _parse_company(self, company: Dict[str, Any]) -> StartupRecord | None:
        """Parses a single company object into a StartupRecord."""
        try:
            name = company.get("name")
            if not name:
                return None
                
            slug = company.get("slug")
            if slug:
                source_url = f"https://www.ycombinator.com/companies/{slug}"
            else:
                return None
                
            # Employee count
            team_size = company.get("team_size")
            if team_size is not None:
                try:
                    team_size = int(team_size)
                    if team_size < 0:
                        team_size = None
                except (ValueError, TypeError):
                    team_size = None
                    
            return StartupRecord(
                source=Source(
                    name="Y Combinator",
                    url=source_url
                ),
                content=StartupContent(
                    entityName=name,
                    data=StartupContentData(
                        employeeCount=team_size
                    )
                )
            )
        except Exception as e:
            logger.debug(f"Failed to parse YC company: {e}")
            return None
