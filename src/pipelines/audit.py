import logging
import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.database.connection import get_session
from src.database.models import ResearchPaper, Startup, Product

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
            
    async with get_session() as session:
        # --- STARTUPS AUDIT ---
        stmt_s = select(func.count(Startup.id))
        total_startups = (await session.execute(stmt_s)).scalar()
        
        stmt_s_invalid = select(func.count(Startup.id)).where(
            (Startup.entity_name.is_(None)) | (Startup.entity_name == "") | 
            (Startup.source_url.is_(None)) | (Startup.source_url == "")
        )
        total_s_invalid = (await session.execute(stmt_s_invalid)).scalar()
        
        stmt_s_null_emp = select(func.count(Startup.id)).where(Startup.employee_count.is_(None))
        total_s_null_emp = (await session.execute(stmt_s_null_emp)).scalar()
        
        # --- PRODUCTS AUDIT ---
        stmt_p = select(func.count(Product.id))
        total_products = (await session.execute(stmt_p)).scalar()
        
        stmt_p_invalid = select(func.count(Product.id)).where(
            (Product.startup_name.is_(None)) | (Product.startup_name == "") |
            (Product.pricing_model.is_(None)) | (Product.source_url.is_(None))
        )
        total_p_invalid = (await session.execute(stmt_p_invalid)).scalar()
        
        logger.info("=== STARTUPS AUDIT RESULTS ===")
        logger.info(f"Total Startups in DB: {total_startups}")
        logger.info(f"Invalid Startups (Missing Name/URL): {total_s_invalid}")
        logger.info(f"Startups with Missing Employee Count: {total_s_null_emp}")
        logger.info("==============================")
        
        logger.info("=== PRODUCTS AUDIT RESULTS ===")
        logger.info(f"Total Products in DB: {total_products}")
        logger.info(f"Invalid Products (Missing Provider/Pricing/URL): {total_p_invalid}")
        logger.info("==============================")
        
        if total_s_invalid > 0 or total_p_invalid > 0:
            logger.error(f"AUDIT FAILED: Found invalid startup/product records.")
            return False
            
        if total_startups > 0 and total_startups < 1000:
            logger.error(f"AUDIT FAILED: Startup count {total_startups} < 1000.")
            return False
            
        if total_products > 0 and total_products < 1000:
            logger.error(f"AUDIT FAILED: Product count {total_products} < 1000.")
            return False
            
        return True
