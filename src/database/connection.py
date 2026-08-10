import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import get_settings
from src.core.exceptions import DatabaseError, ConfigurationError
from src.database.models import Base

logger = logging.getLogger(__name__)

# Global instances for connection pooling
_engine = None
_sessionmaker = None


def get_engine():
    """Get the SQLAlchemy engine instance. Creates it if it doesn't exist."""
    global _engine
    if _engine is None:
        try:
            settings = get_settings()
            if not settings.DATABASE_URL:
                raise ConfigurationError("DATABASE_URL is not configured")
                
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=(settings.LOG_LEVEL == "DEBUG"),
                future=True,
                pool_pre_ping=True
            )
        except ConfigurationError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to create database engine: {str(e)}") from e
            
    return _engine


def get_session_factory():
    """Get the async session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        engine = get_engine()
        _sessionmaker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for yielding database sessions.
    Handles commit on success and rollback on exception.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise DatabaseError(f"Session transaction failed: {str(e)}") from e
    except Exception as e:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    Does NOT destroy existing data.
    """
    logger.info("Initializing database...")
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Create tables only if they don't exist
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise DatabaseError(f"Failed to initialize database tables: {str(e)}") from e


async def close_db() -> None:
    """
    Close the database connection pool cleanly.
    """
    global _engine
    if _engine is not None:
        logger.info("Disposing database engine...")
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed.")
