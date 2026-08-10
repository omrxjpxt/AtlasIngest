import pytest
import os
from pydantic import ValidationError

from src.config.settings import Settings, get_settings
from src.core.exceptions import ConfigurationError

def test_settings_load_valid(monkeypatch):
    """Test that settings load correctly when all required vars are present."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    settings = Settings()
    
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.ENVIRONMENT == "production"
    assert settings.APP_NAME == "IntelligenceForge"

def test_settings_missing_database_url(monkeypatch):
    """Test that missing DATABASE_URL raises validation error."""
    # Ensure DATABASE_URL is not set
    monkeypatch.delenv("DATABASE_URL", raising=False)
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
        
    assert "DATABASE_URL" in str(exc_info.value)

def test_settings_invalid_log_level(monkeypatch):
    """Test that invalid LOG_LEVEL raises validation error."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    monkeypatch.setenv("LOG_LEVEL", "INVALID")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
        
    assert "LOG_LEVEL must be one of" in str(exc_info.value)

def test_get_settings_caching(monkeypatch):
    """Test that get_settings caches the Settings instance."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")
    
    # clear cache for test isolation
    get_settings.cache_clear()
    
    settings_1 = get_settings()
    settings_2 = get_settings()
    
    assert settings_1 is settings_2
    
def test_get_settings_raises_configuration_error(monkeypatch):
    """Test that get_settings wraps ValidationErrors in our ConfigurationError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    
    with pytest.raises(ConfigurationError):
        get_settings()
