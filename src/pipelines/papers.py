import logging
import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.arxiv import ArxivAdapter
from src.crawlers.adapters.huggingface import HuggingFaceAdapter
from src.enrichment.github import GitHubEnricher
from src.database.connection import get_session
from src.database.models import ResearchPaper

logger = logging.getLogger(__name__)

class PaperPipeline:
    def __init__(self):
        self.settings = get_settings()
        self.engine = CrawlerEngine(
            verify_ssl=self.settings.CRAWLER_VERIFY_SSL
        )
        self.arxiv = ArxivAdapter(self.engine, batch_size=self.settings.PAPER_DISCOVERY_BATCH_SIZE)
        self.hf = HuggingFaceAdapter(self.engine)
        self.github = GitHubEnricher()
        
    async def _paper_exists(self, session, paper_url: str, arxiv_id: str) -> bool:
        stmt = select(ResearchPaper).where(
            (ResearchPaper.paper_url == paper_url) | 
            (ResearchPaper.arxiv_id == arxiv_id)
        )
        result = await session.execute(stmt)
        return result.first() is not None

    async def run(self, target_count: int = None):
        target = target_count or self.settings.PAPER_TARGET_COUNT
        
        logger.info(f"Starting Paper Ingestion Pipeline. Target: {target} papers.")
        
        await self.engine.start()
        await self.github.start()
        
        offset = 0
        saved_count = 0
        total_discovered = 0
        
        try:
            while saved_count < target:
                logger.info(f"Fetching arXiv batch starting at offset {offset}...")
                batch_records = await self.arxiv.fetch_batch(offset)
                
                if not batch_records:
                    logger.warning("No more records returned from arXiv or an error occurred. Stopping.")
                    break
                    
                total_discovered += len(batch_records)
                logger.info(f"Discovered {len(batch_records)} papers in this batch. Total discovered: {total_discovered}.")
                
                # Process the batch concurrently
                tasks = [
                    self.process_record(record, arxiv_id)
                    for record, arxiv_id in batch_records
                ]
                
                results = await asyncio.gather(*tasks)
                
                for success in results:
                    if success:
                        saved_count += 1
                        if saved_count >= target:
                            break
                            
                logger.info(f"Progress: {saved_count}/{target} valid papers saved.")
                offset += self.settings.PAPER_DISCOVERY_BATCH_SIZE
                
                # Sleep briefly between batches to respect API limits
                await asyncio.sleep(3)
                
        finally:
            await self.engine.close()
            await self.github.close()
            
        logger.info(f"Pipeline finished. Total saved: {saved_count}")

    async def process_record(self, record, arxiv_id: str) -> bool:
        """
        Process a single paper record: map GitHub repo, get stars, and save to DB.
        Returns True if successfully saved, False otherwise (e.g. duplicate or invalid).
        """
        # 1. Validation
        if not record.content.title or not record.content.paper_url:
            return False
            
        # 2. Fast Deduplication Check
        async with get_session() as session:
            if await self._paper_exists(session, str(record.content.paper_url), arxiv_id):
                return False
                
        # 3. HF Code Mapping
        github_url = await self.hf.get_github_url(arxiv_id)
        
        # 4. GitHub Enrichment
        github_stars = None
        if github_url:
            github_stars = await self.github.get_stars(github_url)
            
        # 5. DB Persistence
        async with get_session() as session:
            try:
                db_paper = ResearchPaper(
                    title=record.content.title,
                    authors=record.content.authors,
                    paper_url=str(record.content.paper_url),
                    arxiv_id=arxiv_id,
                    source_name=record.source.name,
                    github_url=github_url,
                    github_stars=github_stars,
                    published_date=record.content.published_date
                )
                session.add(db_paper)
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False
            except Exception as e:
                logger.error(f"Error saving paper {arxiv_id}: {e}")
                await session.rollback()
                return False
