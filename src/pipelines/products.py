import logging
from sqlalchemy import select

from src.config.settings import get_settings
from src.crawlers.engine import CrawlerEngine
from src.crawlers.adapters.futurepedia_products import FuturepediaProductAdapter
from src.crawlers.adapters.aifoxx_products import AifoxxProductAdapter
from src.crawlers.adapters.aitoptools_products import AITopToolsAdapter
from src.database.connection import get_session
from src.database.models import Startup, Product
from src.pipelines.entity_normalization import normalize_entity_name

logger = logging.getLogger(__name__)

class ProductPipeline:
    
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
        
    async def _process_record(self, record, product_name, stats, session):
        if not record.content.startupName:
            stats["owner_unresolved"] += 1
            stats["rejected"] += 1
            return
            
        if not record.content.pricingModel:
            stats["pricing_unresolved"] += 1
            stats["rejected"] += 1
            return
            
        stmt = select(Product).where(
            (Product.source_url == str(record.source.url)) |
            (Product.product_name == product_name)
        )
        existing = (await session.execute(stmt)).scalars().first()
        
        if existing:
            stats["duplicates"] += 1
            return
            
        normalized_owner = normalize_entity_name(record.content.startupName)
        
        product = Product(
            startup_name=normalized_owner,
            product_name=product_name,
            pricing_model=record.content.pricingModel.value,
            source_url=str(record.source.url)
        )
        
        session.add(product)
        try:
            await session.commit()
            stats["valid"] += 1
            stats["final_stored"] += 1
        except Exception as e:
            logger.error(f"Failed to store product {normalized_owner}: {e}")
            await session.rollback()
            stats["rejected"] += 1
        
    async def run(self, target_count: int = 1200):
        logger.info(f"Starting Phase 4: Product Ingestion with target {target_count}")
        
        stats = {
            "discovered": 0,
            "valid": 0,
            "duplicates": 0,
            "rejected": 0,
            "owner_unresolved": 0,
            "pricing_unresolved": 0,
            "final_stored": 0
        }
        
        await self.engine.start()
        try:
            # Futurepedia (Legitimate valid products currently at 86)
            # fp_adapter = FuturepediaProductAdapter(engine=self.engine)
            # logger.info("Running Futurepedia Product Adapter...")
            
            # async for record, product_name in fp_adapter.fetch_and_parse_all(target_count=15):
            #     if stats["valid"] >= target_count:
            #         break
                    
            #     stats["discovered"] += 1
            #     async with get_session() as session:
            #         await self._process_record(record, product_name, stats, session)
            
            
            # AIFOXX is skipped for this final emergency run

                    
            # AITopTools Fallback
            if stats["valid"] < target_count:
                ait_adapter = AITopToolsAdapter(engine=self.engine)
                needed = target_count - stats["valid"]
                logger.info(f"Running AITopTools Adapter for {needed} products...")
                
                async for record, product_name in ait_adapter.fetch_and_parse_all(target_count=needed):
                    if stats["valid"] >= target_count:
                        break
                        
                    stats["discovered"] += 1
                    async with get_session() as session:
                        await self._process_record(record, product_name, stats, session)
                        
        finally:
            await self.engine.close()
            
        logger.info("=== PRODUCT INGESTION STATISTICS ===")
        logger.info(f"Discovered: {stats['discovered']}")
        logger.info(f"Valid: {stats['valid']}")
        logger.info(f"Duplicates: {stats['duplicates']}")
        logger.info(f"Rejected: {stats['rejected']}")
        logger.info(f"Owner unresolved: {stats['owner_unresolved']}")
        logger.info(f"Pricing unresolved: {stats['pricing_unresolved']}")
        logger.info(f"Final stored: {stats['final_stored']}")
        logger.info("====================================")
