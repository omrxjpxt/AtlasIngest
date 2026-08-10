import asyncio
import logging
from typing import List, Optional
import uuid

from src.crawlers.models import CrawlRequest, CrawlResult
from src.crawlers.client import AsyncHttpClient
from src.crawlers.retry import RetryEngine
from src.crawlers.url_utils import canonicalize_url, hash_content
from src.crawlers.persistence import save_raw_document, create_crawl_run, complete_crawl_run
from src.database.connection import get_session
from src.database.models import CrawlRun

logger = logging.getLogger(__name__)

class CrawlerEngine:
    def __init__(
        self,
        global_concurrency: int = 20,
        per_host_concurrency: int = 5,
        total_timeout: int = 30,
        connect_timeout: int = 10,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
        user_agent: str = "IntelligenceForge/0.1",
        verify_ssl: bool = True
    ):
        self.global_semaphore = asyncio.Semaphore(global_concurrency)
        self.client = AsyncHttpClient(
            global_concurrency=global_concurrency,
            per_host_concurrency=per_host_concurrency,
            total_timeout=total_timeout,
            connect_timeout=connect_timeout,
            user_agent=user_agent,
            verify_ssl=verify_ssl
        )
        self.retry_engine = RetryEngine(
            max_retries=max_retries,
            base_delay=base_backoff,
            max_delay=max_backoff
        )

    async def start(self):
        await self.client.start()
        logger.info("CrawlerEngine started.")

    async def close(self):
        await self.client.close()
        logger.info("CrawlerEngine stopped.")

    async def fetch_with_retry(self, request: CrawlRequest) -> CrawlResult:
        result = CrawlResult(requested_url=request.url)
        
        for attempt in range(self.retry_engine.max_retries + 1):
            result.retry_count = attempt
            
            async with self.global_semaphore:
                raw_html, status_code, content_type, final_url, response_time, error, retry_after = await self.client.fetch(request.url)
            
            result.status_code = status_code
            result.content_type = content_type
            result.final_url = final_url
            result.response_time_ms = int(response_time) if response_time else None
            
            if error:
                result.error = error
                if attempt < self.retry_engine.max_retries:
                    await self.retry_engine.sleep_for_retry(attempt, retry_after=retry_after)
                    continue
                else:
                    break
            
            if status_code is not None:
                if 200 <= status_code < 300:
                    result.success = True
                    result.raw_html = raw_html
                    break
                elif self.retry_engine.is_retryable_status(status_code):
                    result.error = f"HTTP {status_code}"
                    if attempt < self.retry_engine.max_retries:
                        await self.retry_engine.sleep_for_retry(attempt, retry_after=retry_after)
                        continue
                    else:
                        break
                else:
                    result.error = f"HTTP {status_code}"
                    break
                    
        if result.success and result.raw_html:
            result.content_hash = hash_content(result.raw_html)
            
        return result

    async def process_request(self, request: CrawlRequest, crawl_run_id: Optional[uuid.UUID] = None) -> CrawlResult:
        logger.info(f"Processing request for {request.url}")
        
        result = await self.fetch_with_retry(request)
        
        if result.success:
            canonical = canonicalize_url(result.final_url or result.requested_url)
            try:
                saved = await save_raw_document(
                    crawl_run_id=crawl_run_id,
                    source_url=result.requested_url,
                    canonical_url=canonical,
                    content_hash=result.content_hash,
                    raw_html=result.raw_html,
                    status="EXTRACTED" if result.success else "FAILED"  # PENDING or similar logic based on your phase 1 setup. Let's use PENDING as it's raw text
                )
                if saved:
                    logger.info(f"Successfully saved raw document for {request.url}")
            except Exception as e:
                logger.error(f"Failed to persist document for {request.url}: {e}")
        else:
            logger.warning(f"Failed to fetch {request.url}: {result.error}")
            
        return result

    async def process_batch(self, requests: List[CrawlRequest], source_id: Optional[uuid.UUID] = None) -> List[CrawlResult]:
        crawl_run_id = None
        if source_id:
            crawl_run_id = await create_crawl_run(source_id)
            
        tasks = [self.process_request(req, crawl_run_id) for req in requests]
        results = await asyncio.gather(*tasks)
        
        if crawl_run_id:
            successes = sum(1 for r in results if r.success)
            errors = len(results) - successes
            status = "COMPLETED" if errors == 0 else "PARTIAL" if successes > 0 else "FAILED"
            await complete_crawl_run(crawl_run_id, status, successes, errors)
            
        return results
