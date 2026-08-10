import logging
from typing import Optional
import json

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest

logger = logging.getLogger(__name__)

class HuggingFaceAdapter:
    """
    Adapter for querying Hugging Face Papers API to find explicit paper to 
    GitHub repository mappings using arXiv IDs.
    """
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.base_url = "https://huggingface.co/api/papers"

    async def get_github_url(self, arxiv_id: str) -> Optional[str]:
        """
        Queries HF Papers API for a given arXiv ID and extracts the githubRepo.
        Returns the GitHub URL if found, else None.
        """
        url = f"{self.base_url}/{arxiv_id}"
        req = CrawlRequest(url=url)
        
        # We can use the crawler engine to fetch this API resiliently
        result = await self.engine.fetch_with_retry(req)
        
        if not result.success or not result.raw_html:
            # 404 is common if HF hasn't indexed the paper or it has no code
            if result.status_code != 404:
                logger.warning(f"HF API lookup failed for {arxiv_id}: {result.status_code}")
            return None
            
        try:
            data = json.loads(result.raw_html)
            github_url = data.get("githubRepo")
            if github_url and isinstance(github_url, str) and github_url.startswith("https://github.com/"):
                return github_url
        except json.JSONDecodeError:
            logger.error(f"Failed to parse HF API response for {arxiv_id}")
            
        return None
