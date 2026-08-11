import logging
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.jobs_adapter import JobsAdapter
from src.database.connection import get_session
from src.database.models import Job

logger = logging.getLogger(__name__)

class JobPipeline:
    def __init__(self):
        self.settings = get_settings()
        self.engine = CrawlerEngine(
            global_concurrency=self.settings.CRAWLER_GLOBAL_CONCURRENCY,
            per_host_concurrency=self.settings.CRAWLER_PER_HOST_CONCURRENCY,
            total_timeout=self.settings.CRAWLER_TIMEOUT_SECONDS,
            connect_timeout=self.settings.CRAWLER_TIMEOUT_SECONDS,
            max_retries=self.settings.CRAWLER_MAX_RETRIES,
            verify_ssl=self.settings.CRAWLER_VERIFY_SSL
        )
        
    async def _process_record(self, record, title, stats, session):
        stmt = select(Job).where(
            (Job.source_url == str(record.source.url)) |
            ((Job.role == title) & (Job.company == record.content.company))
        )
        existing = (await session.execute(stmt)).scalars().first()
        
        if existing:
            stats["duplicates"] += 1
            return
            
        job = Job(
            company=record.content.company,
            role=record.content.role,
            role_family=record.content.role_family,
            is_remote=record.content.is_remote,
            date=record.content.date,
            location=record.content.location,
            source_url=str(record.source.url)
        )
        
        session.add(job)
        try:
            await session.commit()
            stats["valid"] += 1
            stats["final_stored"] += 1
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to commit Job {title}: {e}")
            stats["rejected"] += 1

    async def run(self):
        logger.info("Starting Job Collection Pipeline (Phase 5)...")
        stats = {
            "discovered": 0,
            "valid": 0,
            "duplicates": 0,
            "rejected": 0,
            "stale": 0,
            "future_dated": 0,
            "final_stored": 0,
            "source_breakdown": {}
        }
        
        await self.engine.start()
        try:
            adapter = JobsAdapter(engine=self.engine)
            async for record, title in adapter.fetch_and_parse_all():
                stats["discovered"] += 1
                
                src = record.source.name
                stats["source_breakdown"][src] = stats["source_breakdown"].get(src, 0) + 1
                
                async with get_session() as session:
                    await self._process_record(record, title, stats, session)
        finally:
            await self.engine.stop()
            
        logger.info("=== JOB INGESTION STATISTICS ===")
        for k, v in stats.items():
            if k == "source_breakdown":
                logger.info("Source breakdown:")
                for src_name, count in v.items():
                    logger.info(f"  {src_name}: {count}")
            else:
                logger.info(f"{k.capitalize()}: {v}")
        logger.info("====================================")
        
        return stats
