import logging
import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.database.connection import get_session
from src.database.models import ResearchPaper

logger = logging.getLogger(__name__)

async def run_audit():
    """
    Validates data quality of collected research papers.
    """
    logger.info("Starting Research Papers Data Quality Audit...")
    
    async with get_session() as session:
        # Total papers
        stmt = select(func.count(ResearchPaper.id))
        total = (await session.execute(stmt)).scalar()
        
        # Papers with GitHub links
        stmt_gh = select(func.count(ResearchPaper.id)).where(ResearchPaper.github_url.isnot(None))
        total_gh = (await session.execute(stmt_gh)).scalar()
        
        # Papers with GitHub stars
        stmt_stars = select(func.count(ResearchPaper.id)).where(ResearchPaper.github_stars.isnot(None))
        total_stars = (await session.execute(stmt_stars)).scalar()
        
        # Invalid: Missing Title or URL
        stmt_invalid = select(func.count(ResearchPaper.id)).where(
            (ResearchPaper.title.is_(None)) | (ResearchPaper.title == "") | 
            (ResearchPaper.paper_url.is_(None)) | (ResearchPaper.paper_url == "")
        )
        total_invalid = (await session.execute(stmt_invalid)).scalar()
        
        logger.info("=== AUDIT RESULTS ===")
        logger.info(f"Total Papers in DB: {total}")
        gh_percentage = (total_gh/total*100) if total > 0 else 0.0
        logger.info(f"Papers with GitHub URL: {total_gh} ({gh_percentage:.1f}%)")
        logger.info(f"Papers with GitHub Stars: {total_stars}")
        logger.info(f"Invalid Papers (Missing Title/URL): {total_invalid}")
        logger.info("=====================")
        
        if total_invalid > 0:
            logger.error(f"AUDIT FAILED: Found {total_invalid} invalid records.")
            return False
            
        return True
