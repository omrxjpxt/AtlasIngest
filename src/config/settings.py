from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import logging

from src.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    APP_NAME: str = Field(default="IntelligenceForge")
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    # Database
    DATABASE_URL: str
    
    # External APIs (Optional for Phase 1)
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GOOGLE_SHEETS_CREDENTIALS: Optional[str] = None
    
    # Crawler
    CRAWLER_GLOBAL_CONCURRENCY: int = Field(default=20)
    CRAWLER_PER_HOST_CONCURRENCY: int = Field(default=5)
    CRAWLER_TIMEOUT_SECONDS: int = Field(default=30)
    CRAWLER_CONNECT_TIMEOUT_SECONDS: int = Field(default=10)
    CRAWLER_MAX_RETRIES: int = Field(default=3)
    CRAWLER_BASE_BACKOFF_SECONDS: float = Field(default=1.0)
    CRAWLER_MAX_BACKOFF_SECONDS: float = Field(default=30.0)
    CRAWLER_USER_AGENT: str = Field(default="IntelligenceForge/0.1")
    CRAWLER_VERIFY_SSL: bool = Field(default=True)
    
    # Phase 3 Configuration
    PAPER_TARGET_COUNT: int = Field(default=1200)
    PAPER_DISCOVERY_BATCH_SIZE: int = Field(default=100)
    GITHUB_CONCURRENCY: int = Field(default=5)
    GITHUB_MAX_RETRIES: int = Field(default=3)
    GITHUB_TOKEN: Optional[str] = Field(default=None)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return upper_v
        
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        # Ensure it's using the asyncpg driver if it's postgres
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")
        return v

@lru_cache()
def get_settings() -> Settings:
    """
    Load and cache settings.
    Raises ConfigurationError if required settings (like DATABASE_URL) are missing.
    """
    try:
        return Settings()
    except Exception as e:
        # Wrap pydantic validation errors in our custom exception
        raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
