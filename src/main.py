import argparse
import asyncio
import logging
import sys

from src.config.settings import get_settings
from src.core.logging import setup_logging
from src.core.exceptions import ConfigurationError, DatabaseError
from src.database.connection import init_db, close_db
from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest

logger = logging.getLogger(__name__)

async def main():
    """
    Main application entrypoint.
    Validates configuration, sets up logging, and initializes the database.
    """
    try:
        # 1. Load configuration
        settings = get_settings()
        
        # 2. Initialize logging
        # Convert string log level (e.g., 'INFO') to logging module integer
        log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
        setup_logging(level=log_level)
        
        logger.info(f"Starting {settings.APP_NAME} (Phase 1) in {settings.ENVIRONMENT} mode")
        
        # 3. Validate required configuration
        # This is already handled implicitly by get_settings() which will raise ConfigurationError
        # if Pydantic fails to validate the required fields (like DATABASE_URL).
        
        # 4. Initialize the database connection
        await init_db()
        
        # Parse CLI arguments
        parser = argparse.ArgumentParser(description="IntelligenceForge CLI")
        subparsers = parser.add_subparsers(dest="command")
        
        crawl_parser = subparsers.add_parser("crawl", help="Run the crawler on a specific URL")
        crawl_parser.add_argument("--url", required=True, help="URL to crawl")
        
        papers_parser = subparsers.add_parser("papers", help="Run Phase 3: Research Paper Ingestion")
        papers_parser.add_argument("--target", type=int, help="Target number of papers to collect")
        
        startups_parser = subparsers.add_parser("startups", help="Run Phase 4: AI Startup Ingestion")
        startups_parser.add_argument("--target", type=int, default=1200, help="Target number of startups to collect")
        
        products_parser = subparsers.add_parser("products", help="Run Phase 4: AI Product Ingestion")
        products_parser.add_argument("--target", type=int, default=1200, help="Target number of products to collect")
        
        audit_parser = subparsers.add_parser("audit", help="Run Data Quality Audit on Research Papers, Startups, and Products")
        
        export_parser = subparsers.add_parser("export", help="Export valid papers to JSONL")
        export_parser.add_argument("--format", default="jsonl", help="Export format")
        
        args = parser.parse_args()
        
        if args.command == "crawl":
            logger.info(f"Starting crawl for {args.url}")
            engine = CrawlerEngine(
                global_concurrency=settings.CRAWLER_GLOBAL_CONCURRENCY,
                per_host_concurrency=settings.CRAWLER_PER_HOST_CONCURRENCY,
                total_timeout=settings.CRAWLER_TIMEOUT_SECONDS,
                connect_timeout=settings.CRAWLER_CONNECT_TIMEOUT_SECONDS,
                max_retries=settings.CRAWLER_MAX_RETRIES,
                base_backoff=settings.CRAWLER_BASE_BACKOFF_SECONDS,
                max_backoff=settings.CRAWLER_MAX_BACKOFF_SECONDS,
                user_agent=settings.CRAWLER_USER_AGENT,
                verify_ssl=settings.CRAWLER_VERIFY_SSL
            )
            await engine.start()
            try:
                request = CrawlRequest(url=args.url)
                result = await engine.process_request(request)
                if result.success:
                    logger.info(f"Crawl successful. Fetched {len(result.raw_html or '')} bytes.")
                else:
                    logger.error(f"Crawl failed: {result.error}")
            finally:
                await engine.close()
                
        elif args.command == "papers":
            from src.pipelines.papers import PaperPipeline
            pipeline = PaperPipeline()
            await pipeline.run(target_count=args.target)
            
        elif args.command == "startups":
            from src.pipelines.startups import StartupPipeline
            pipeline = StartupPipeline()
            await pipeline.run(target_count=args.target)
            
        elif args.command == "products":
            from src.pipelines.products import ProductPipeline
            pipeline = ProductPipeline()
            await pipeline.run(target_count=args.target)
            
        elif args.command == "audit":
            from src.pipelines.audit import run_audit
            success = await run_audit()
            if not success:
                sys.exit(1)
                
        elif args.command == "export":
            from src.pipelines.export import run_export, run_export_startups, run_export_products
            # Only jsonl is currently supported but we accept the format flag
            await run_export()
            await run_export_startups()
            await run_export_products()
            
        else:
            # 5. Perform a basic health/startup check
            logger.info("IntelligenceForge ready. Use one of the subcommands (crawl, papers, startups, products, audit, export).")
        
    except ConfigurationError as e:
        # Fallback print if logging isn't fully set up yet
        print(f"CRITICAL: Configuration Error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except DatabaseError as e:
        logger.error(f"CRITICAL: Database Error: {e.message}")
        sys.exit(1)
    except Exception as e:
        if logger:
            logger.critical(f"CRITICAL: Unexpected error: {str(e)}", exc_info=True)
        else:
            print(f"CRITICAL: Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 6. Shut down cleanly
        try:
            await close_db()
        except Exception:
            pass
        logger.info("Application stopped.")

if __name__ == "__main__":
    asyncio.run(main())
