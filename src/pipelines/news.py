import logging
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.news_adapter import NewsAdapter
from src.database.connection import get_session
from src.database.models import News

logger = logging.getLogger(__name__)

class NewsPipeline:
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
        stmt = select(News).where(
            (News.url == str(record.url)) |
            ((News.title == title) & (News.source_name == record.source.name))
        )
        existing = (await session.execute(stmt)).scalars().first()

        if existing:
            stats["duplicates"] += 1
            return

        # 1. Fetch full text using crawler engine
        from src.crawlers.engine import CrawlRequest
        req = CrawlRequest(url=str(record.url))
        res = await self.engine.process_request(req)

        # 2. Determine if LLM fallback is needed (missing date or poor summary)
        published_date = record.published_date
        summary = record.summary

        if res.success and res.raw_html:
            if not published_date or not summary or len(summary) < 50:
                from src.extraction.llm_engine import LLMEngine
                from src.models.schemas import NewsContent
                from src.database.models import ExtractionRun
                import uuid

                llm = LLMEngine()
                extracted_data, audit = await llm.extract(res.raw_html, NewsContent, context="Extract the news publication date and a 2-3 sentence summary.")

                if extracted_data:
                    if not published_date and extracted_data.published_date:
                        published_date = extracted_data.published_date
                    if extracted_data.summary:
                        summary = extracted_data.summary

                # Log audit metadata
                run = ExtractionRun(
                    crawl_run_id=None,
                    status="COMPLETED" if extracted_data else "FAILED",
                    model_used=audit.get("provider_used") or "none",
                    audit_metadata=audit
                )
                session.add(run)

        # Still require date to proceed?
        if not published_date:
            stats["rejected"] += 1
            return

        news_item = News(
            title=record.title,
            url=str(record.url),
            summary=summary,
            published_date=published_date,
            source_name=record.source.name
        )

        session.add(news_item)
        try:
            await session.commit()
            stats["valid"] += 1
            stats["final_stored"] += 1
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to commit News {title}: {e}")
            stats["rejected"] += 1

    async def run(self):
        logger.info("Starting News Collection Pipeline (Phase 5)...")
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
            adapter = NewsAdapter(engine=self.engine)
            async for record, title in adapter.fetch_and_parse_all():
                stats["discovered"] += 1

                src = record.source.name
                stats["source_breakdown"][src] = stats["source_breakdown"].get(src, 0) + 1

                async with get_session() as session:
                    await self._process_record(record, title, stats, session)
        finally:
            await self.engine.close()

        logger.info("=== NEWS INGESTION STATISTICS ===")
        for k, v in stats.items():
            if k == "source_breakdown":
                logger.info("Source breakdown:")
                for src_name, count in v.items():
                    logger.info(f"  {src_name}: {count}")
            else:
                logger.info(f"{k.capitalize()}: {v}")
        logger.info("====================================")

        return stats
