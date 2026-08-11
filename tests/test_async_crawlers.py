import pytest
from unittest.mock import AsyncMock, patch
from src.crawlers.client import AsyncHttpClient
from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
import aiohttp
import asyncio

class MockResponse:
    def __init__(self, status, text_data, url, headers=None):
        self.status = status
        self._text = text_data
        self.url = url
        self.headers = headers or {}
        
    async def text(self):
        return self._text
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture
def mock_session_get():
    with patch('aiohttp.ClientSession.request') as mock_get:
        yield mock_get

@pytest.mark.asyncio
async def test_async_client_success(mock_session_get):
    url = "https://example.com"
    mock_session_get.return_value = MockResponse(
        status=200, 
        text_data="<html>Success</html>", 
        url=url, 
        headers={'Content-Type': 'text/html'}
    )
    
    client = AsyncHttpClient()
    await client.start()
    
    raw_html, status_code, content_type, final_url, response_time, error, retry_after = await client.fetch(url)
    
    assert status_code == 200
    assert raw_html == "<html>Success</html>"
    assert not error
    
    await client.close()

@pytest.mark.asyncio
async def test_engine_retries_on_500(mock_session_get):
    url = "https://example.com/fail"
    
    # First two fail, third succeeds
    mock_session_get.side_effect = [
        MockResponse(status=500, text_data="", url=url),
        MockResponse(status=502, text_data="", url=url),
        MockResponse(status=200, text_data="<html>Finally!</html>", url=url)
    ]
    
    # Use very small backoff for test speed
    engine = CrawlerEngine(max_retries=3, base_backoff=0.01, max_backoff=0.05)
    await engine.start()
    
    req = CrawlRequest(url=url)
    result = await engine.fetch_with_retry(req)
    
    assert result.success is True
    assert result.status_code == 200
    assert result.retry_count == 2
    assert result.raw_html == "<html>Finally!</html>"
    
    await engine.close()

@pytest.mark.asyncio
async def test_engine_fails_after_max_retries(mock_session_get):
    url = "https://example.com/always-fail"
    
    # Always fail
    mock_session_get.return_value = MockResponse(status=503, text_data="", url=url)
    
    engine = CrawlerEngine(max_retries=2, base_backoff=0.01, max_backoff=0.05)
    await engine.start()
    
    req = CrawlRequest(url=url)
    result = await engine.fetch_with_retry(req)
    
    assert result.success is False
    assert result.status_code == 503
    assert result.retry_count == 2
    assert result.error == "HTTP 503"
    
    await engine.close()

@pytest.mark.asyncio
async def test_engine_retries_on_429_with_retry_after(mock_session_get):
    url = "https://example.com/rate-limit"
    
    # 429 then 200
    mock_session_get.side_effect = [
        MockResponse(status=429, text_data="", url=url, headers={'Retry-After': '0.1'}),
        MockResponse(status=200, text_data="<html>OK</html>", url=url)
    ]
    
    engine = CrawlerEngine(max_retries=1, base_backoff=0.01, max_backoff=0.05)
    await engine.start()
    
    req = CrawlRequest(url=url)
    result = await engine.fetch_with_retry(req)
    
    assert result.success is True
    assert result.status_code == 200
    assert result.retry_count == 1
    
    await engine.close()

@pytest.mark.asyncio
async def test_engine_does_not_retry_404(mock_session_get):
    url = "https://example.com/not-found"
    mock_session_get.return_value = MockResponse(status=404, text_data="", url=url)
    
    engine = CrawlerEngine(max_retries=3)
    await engine.start()
    
    req = CrawlRequest(url=url)
    result = await engine.fetch_with_retry(req)
    
    assert result.success is False
    assert result.status_code == 404
    assert result.retry_count == 0  # No retries for 404
    
    await engine.close()
