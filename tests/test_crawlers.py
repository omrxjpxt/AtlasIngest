import pytest
from src.crawlers.url_utils import canonicalize_url, hash_content
from src.crawlers.retry import RetryEngine

def test_canonicalize_url_removes_fragments():
    url = "https://example.com/page#section"
    assert canonicalize_url(url) == "https://example.com/page"

def test_canonicalize_url_lowercases_host():
    url = "https://EXAMPLE.com/page"
    assert canonicalize_url(url) == "https://example.com/page"

def test_canonicalize_url_removes_tracking_params():
    url = "https://example.com/page?utm_source=google&valid=1"
    assert canonicalize_url(url) == "https://example.com/page?valid=1"

def test_canonicalize_url_removes_trailing_slash():
    url = "https://example.com/page/"
    assert canonicalize_url(url) == "https://example.com/page"

def test_hash_content_deterministic():
    content = "Hello, world!"
    hash1 = hash_content(content)
    hash2 = hash_content(content)
    assert hash1 == hash2
    assert hash1 != hash_content("Different content")

def test_retry_engine_is_retryable():
    engine = RetryEngine()
    assert engine.is_retryable_status(500)
    assert engine.is_retryable_status(502)
    assert engine.is_retryable_status(503)
    assert engine.is_retryable_status(408)
    assert engine.is_retryable_status(429)
    
    assert not engine.is_retryable_status(200)
    assert not engine.is_retryable_status(400)
    assert not engine.is_retryable_status(404)
    assert not engine.is_retryable_status(403)
