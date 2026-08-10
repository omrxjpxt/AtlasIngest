import logging
import asyncio
import aiohttp
import json
import re
from typing import Optional
from datetime import datetime, timezone

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

class GitHubEnricher:
    """
    Enriches papers with GitHub star counts.
    Uses bounded concurrency and respects rate limits.
    """
    def __init__(self):
        self.settings = get_settings()
        self.semaphore = asyncio.Semaphore(self.settings.GITHUB_CONCURRENCY)
        self.max_retries = self.settings.GITHUB_MAX_RETRIES
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = "https://api.github.com/repos"
        
    async def start(self):
        """Initializes the aiohttp ClientSession."""
        if self.session is None:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": self.settings.CRAWLER_USER_AGENT,
            }
            if self.settings.GITHUB_TOKEN:
                headers["Authorization"] = f"token {self.settings.GITHUB_TOKEN}"
                
            verify_ssl = self.settings.CRAWLER_VERIFY_SSL
            if not verify_ssl:
                logger.warning("SSL verification is EXPLICITLY DISABLED for GitHubEnricher.")
                
            connector = aiohttp.TCPConnector(ssl=verify_ssl)
            self.session = aiohttp.ClientSession(headers=headers, connector=connector)
            
    async def close(self):
        """Closes the session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    def _extract_owner_repo(self, github_url: str) -> Optional[tuple[str, str]]:
        # Handle https://github.com/owner/repo
        match = re.search(r'github\.com/([^/]+)/([^/]+)', github_url)
        if match:
            # Strip trailing .git or anything else just in case
            repo = match.group(2).removesuffix(".git")
            return match.group(1), repo
        return None

    async def get_stars(self, github_url: str) -> Optional[int]:
        """
        Fetches the star count for a given GitHub repository URL.
        Returns the star count, or None if not found or on persistent error.
        """
        if not self.session:
            raise RuntimeError("GitHubEnricher session not started.")
            
        owner_repo = self._extract_owner_repo(github_url)
        if not owner_repo:
            return None
            
        owner, repo = owner_repo
        api_url = f"{self.base_url}/{owner}/{repo}"
        
        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    async with self.session.get(api_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("stargazers_count")
                        elif response.status == 404:
                            logger.warning(f"GitHub repo not found: {github_url}")
                            return None
                        elif response.status in (403, 429):
                            # Rate limit hit
                            reset_epoch = response.headers.get("x-ratelimit-reset")
                            if reset_epoch:
                                wait_seconds = max(0, int(reset_epoch) - int(datetime.now(timezone.utc).timestamp()))
                                logger.warning(f"GitHub rate limit hit. Waiting {wait_seconds}s...")
                                await asyncio.sleep(wait_seconds + 1)
                            else:
                                await asyncio.sleep(2 ** attempt)
                        else:
                            # 5xx or others, retry with backoff
                            await asyncio.sleep(2 ** attempt)
                except asyncio.TimeoutError:
                    await asyncio.sleep(2 ** attempt)
                except aiohttp.ClientError as e:
                    logger.error(f"GitHub API client error for {github_url}: {e}")
                    await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    logger.error(f"Unexpected error for {github_url}: {e}")
                    return None
                    
        return None
