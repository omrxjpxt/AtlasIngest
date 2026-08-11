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
    """Test that Settings raises ValidationError when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with monkeypatch.context() as m:
        m.setattr("src.config.settings.Settings.model_config", {"env_file": None})
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
    """Test that get_settings wraps ValidationError in ConfigurationError."""
    get_settings.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with monkeypatch.context() as m:
        m.setattr("src.config.settings.Settings.model_config", {"env_file": None})
        with pytest.raises(ConfigurationError):
            get_settings()
