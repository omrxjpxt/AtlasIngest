import asyncio
import logging
import sys

from src.config.settings import get_settings
from src.core.logging import setup_logging
from src.core.exceptions import ConfigurationError, DatabaseError
from src.database.connection import init_db, close_db

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
        
        # 5. Perform a basic health/startup check
        logger.info("Phase 1 foundation ready. (Scraping and extraction are disabled)")
        
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
