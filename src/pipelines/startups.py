import logging
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.yc_startups import YCStartupAdapter
from src.database.connection import get_session
from src.database.models import Startup
from src.pipelines.entity_normalization import normalize_entity_name

logger = logging.getLogger(__name__)

class StartupPipeline:
    """
    Orchestrates the discovery and storage of AI startups.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
    async def run(self, target_count: int = 1200):
        logger.info(f"Starting Phase 4: Startup Ingestion with target {target_count}")
        
        engine = CrawlerEngine(
            global_concurrency=self.settings.CRAWLER_GLOBAL_CONCURRENCY,
            per_host_concurrency=self.settings.CRAWLER_PER_HOST_CONCURRENCY,
            total_timeout=self.settings.CRAWLER_TIMEOUT_SECONDS,
            connect_timeout=self.settings.CRAWLER_CONNECT_TIMEOUT_SECONDS,
            max_retries=self.settings.CRAWLER_MAX_RETRIES,
            base_backoff=self.settings.CRAWLER_BASE_BACKOFF_SECONDS,
            max_backoff=self.settings.CRAWLER_MAX_BACKOFF_SECONDS,
            user_agent=self.settings.CRAWLER_USER_AGENT,
            verify_ssl=self.settings.CRAWLER_VERIFY_SSL
        )
        
        adapter = YCStartupAdapter(engine=engine)
        
        stats = {
            "discovered": 0,
            "valid": 0,
            "duplicates": 0,
            "rejected": 0,
            "missing_employee_count": 0,
            "final_stored": 0
        }
        
        await engine.start()
        try:
            async for record in adapter.fetch_and_parse_all(target_count=target_count * 2):
                stats["discovered"] += 1
                
                # Check employee count
                if record.content.data.employeeCount is None:
                    stats["missing_employee_count"] += 1
                    
                # Normalize name
                normalized_name = normalize_entity_name(record.content.entityName)
                if not normalized_name:
                    logger.debug(f"Rejected startup due to empty normalized name: {record.content.entityName}")
                    stats["rejected"] += 1
                    continue
                    
                async with get_session() as session:
                    # Deduplication check
                    stmt = select(Startup).where(Startup.entity_name == normalized_name)
                    existing = (await session.execute(stmt)).scalar_one_or_none()
                    
                    if existing:
                        stats["duplicates"] += 1
                        continue
                        
                    # Valid startup, store it
                    startup = Startup(
                        entity_name=normalized_name,
                        employee_count=record.content.data.employeeCount,
                        source_url=str(record.source.url)
                    )
                    # We store the canonical name in the DB if we had a canonical_name column, 
                    # but current models.py has entity_name (which we'll use for normalized).
                    # Wait, the prompt says "Preserve canonical display name = source-verified name. Do not blindly overwrite source names."
                    # I should check models.py: Startup has `entity_name` and no canonical name. I will store the source-verified name in `entity_name`
                    # But then uniqueness constraint is on `entity_name`.
                    # Let's check models.py: `entity_name: Mapped[str] = mapped_column(String, unique=True)`
                    # We will store the original name in `entity_name`, but for querying we'll do case-insensitive search if needed, 
                    # or we can just rely on the existing schema. 
                    # Let's adjust: store the original name in entity_name. We'll do duplicate checking by querying all or normalizing in Python,
                    # but doing it in Python per record might be slow.
                    # Actually, we can check `Startup.source_url == record.source.url` as the primary identity.
                    stmt_url = select(Startup).where(Startup.source_url == str(record.source.url))
                    existing_by_url = (await session.execute(stmt_url)).scalar_one_or_none()
                    
                    if existing_by_url:
                        stats["duplicates"] += 1
                        continue
                        
                    # We will just store the canonical name provided by the source.
                    startup.entity_name = record.content.entityName
                    
                    session.add(startup)
                    try:
                        await session.commit()
                        stats["valid"] += 1
                        stats["final_stored"] += 1
                    except Exception as e:
                        logger.error(f"Failed to store startup {record.content.entityName}: {e}")
                        await session.rollback()
                        stats["rejected"] += 1
                        
                if stats["final_stored"] >= target_count:
                    break
                    
        finally:
            await engine.close()
            
        logger.info("=== STARTUP INGESTION STATISTICS ===")
        for k, v in stats.items():
            logger.info(f"{k.capitalize().replace('_', ' ')}: {v}")
        logger.info("====================================")
