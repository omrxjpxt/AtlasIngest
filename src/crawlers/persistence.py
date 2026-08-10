import logging
from sqlalchemy.exc import IntegrityError
from src.database.connection import get_session
from src.database.models import RawDocument
import uuid
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

async def create_crawl_run(source_id: uuid.UUID) -> uuid.UUID:
    """Creates a new crawl run record and returns its ID."""
    from src.database.models import CrawlRun
    async with get_session() as session:
        run = CrawlRun(source_id=source_id, status="RUNNING")
        session.add(run)
        await session.commit()
        return run.id

async def complete_crawl_run(crawl_run_id: uuid.UUID, status: str, pages_crawled: int, errors_count: int):
    """Marks a crawl run as completed or failed with final stats."""
    from sqlalchemy import select
    from src.database.models import CrawlRun
    async with get_session() as session:
        stmt = select(CrawlRun).where(CrawlRun.id == crawl_run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            run.pages_crawled = pages_crawled
            run.errors_count = errors_count
            run.completed_at = datetime.utcnow()
            await session.commit()


async def save_raw_document(
    crawl_run_id: Optional[uuid.UUID],
    source_url: str,
    canonical_url: Optional[str],
    content_hash: Optional[str],
    raw_html: Optional[str],
    status: str
) -> bool:
    """
    Saves a raw document to the database.
    Handles duplicate detection via IntegrityError (unique constraint on canonical_url + content_hash).
    Returns True if successfully inserted, False if it was a duplicate.
    """
    async with get_session() as session:
        try:
            doc = RawDocument(
                crawl_run_id=crawl_run_id,
                source_url=source_url,
                canonical_url=canonical_url,
                content_hash=content_hash,
                raw_html=raw_html,
                status=status
            )
            session.add(doc)
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            logger.info(f"Duplicate document detected for {canonical_url} with hash {content_hash}. Skipping insertion.")
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to save raw document for {source_url}: {str(e)}")
            raise
