import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.enrichment.github import GitHubEnricher

@pytest.fixture
def mock_settings():
    with patch("src.enrichment.github.get_settings") as mock_get:
        mock_settings = MagicMock()
        mock_settings.GITHUB_CONCURRENCY = 5
        mock_settings.GITHUB_MAX_RETRIES = 3
        mock_settings.GITHUB_TOKEN = None
        mock_settings.CRAWLER_USER_AGENT = "test"
        mock_get.return_value = mock_settings
        yield mock_settings

@pytest.fixture
def enricher(mock_settings):
    return GitHubEnricher()

def test_extract_owner_repo(enricher):
    assert enricher._extract_owner_repo("https://github.com/owner/repo") == ("owner", "repo")
    assert enricher._extract_owner_repo("https://github.com/owner/repo.git") == ("owner", "repo")
    assert enricher._extract_owner_repo("invalid") is None


