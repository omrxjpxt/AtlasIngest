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
                user_agent=settings.CRAWLER_USER_AGENT
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
        else:
            # 5. Perform a basic health/startup check
            logger.info("Phase 2 foundation ready. Use 'crawl --url <url>' to test.")
        
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
