import logging
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.futurepedia_products import FuturepediaProductAdapter
from src.database.connection import get_session
from src.database.models import Startup, Product
from src.pipelines.entity_normalization import normalize_entity_name

logger = logging.getLogger(__name__)

class ProductPipeline:
    """
    Orchestrates the discovery and storage of AI products.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
    async def run(self, target_count: int = 1200):
        logger.info(f"Starting Phase 4: Product Ingestion with target {target_count}")
        
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
        
        adapter = FuturepediaProductAdapter(engine=engine)
        
        stats = {
            "discovered": 0,
            "valid": 0,
            "duplicates": 0,
            "rejected": 0,
            "owner_unresolved": 0,
            "pricing_unresolved": 0,
            "final_stored": 0
        }
        
        await engine.start()
        try:
            async for record, product_name in adapter.fetch_and_parse_all(target_count=target_count * 5):
                stats["discovered"] += 1
                
                # Check for required fields
                if not record.content.startupName:
                    stats["owner_unresolved"] += 1
                    stats["rejected"] += 1
                    continue
                    
                if not record.content.pricingModel:
                    stats["pricing_unresolved"] += 1
                    stats["rejected"] += 1
                    continue
                    
                normalized_startup_name = normalize_entity_name(record.content.startupName)
                
                async with get_session() as session:
                    # Duplicate check by source URL
                    stmt = select(Product).where(Product.source_url == str(record.source.url))
                    existing = (await session.execute(stmt)).scalar_one_or_none()
                    
                    if existing:
                        stats["duplicates"] += 1
                        continue
                        
                    # Deterministic resolution: find if the startup exists
                    # We try exact match first on entity_name
                    stmt_startup = select(Startup).where(Startup.entity_name == record.content.startupName)
                    startup_match = (await session.execute(stmt_startup)).scalar_one_or_none()
                    
                    if not startup_match:
                        # We don't have to require it to exist in the database unless specifically mapped.
                        # The prompt says: "First preserve the source-verified provider name. Then perform deterministic matching against the canonical startup set. If no safe match exists: do not silently map it to another startup."
                        # "Do not require the product's company to already exist in the startup table unless the source relationship explicitly supports that requirement."
                        # So we can just use the provided startupName.
                        pass
                        
                    product = Product(
                        startup_name=record.content.startupName,
                        product_name=product_name,
                        pricing_model=record.content.pricingModel,
                        source_url=str(record.source.url)
                    )
                    
                    session.add(product)
                    try:
                        await session.commit()
                        stats["valid"] += 1
                        stats["final_stored"] += 1
                    except Exception as e:
                        logger.error(f"Failed to store product {record.content.startupName}: {e}")
                        await session.rollback()
                        stats["rejected"] += 1
                        
                if stats["final_stored"] >= target_count:
                    break
                    
        finally:
            await engine.close()
            
        logger.info("=== PRODUCT INGESTION STATISTICS ===")
        for k, v in stats.items():
            logger.info(f"{k.capitalize().replace('_', ' ')}: {v}")
        logger.info("====================================")
