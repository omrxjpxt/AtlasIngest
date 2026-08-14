import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel
from src.extraction.providers.chain import ProviderChain
from src.extraction.providers.base import ProviderError, RateLimitError, PayloadTooLargeError
from src.extraction.llm_engine import LLMEngine

class DummySchema(BaseModel):
    name: str

@pytest.fixture
def mock_chain():
    with patch("src.extraction.providers.chain.GeminiProvider") as mock_gemini, \
         patch("src.extraction.providers.chain.GroqProvider") as mock_groq, \
         patch("src.extraction.providers.chain.DeepSeekProvider") as mock_deepseek:
         
        # Set up mock instances
        mock_gemini_inst = AsyncMock()
        mock_gemini_inst.provider_name = "gemini"
        mock_gemini.return_value = mock_gemini_inst
        
        mock_groq_inst = AsyncMock()
        mock_groq_inst.provider_name = "groq"
        mock_groq.return_value = mock_groq_inst
        
        mock_deepseek_inst = AsyncMock()
        mock_deepseek_inst.provider_name = "deepseek"
        mock_deepseek.return_value = mock_deepseek_inst
        
        chain = ProviderChain(max_retries_per_provider=2)
        chain.providers = [mock_gemini_inst, mock_groq_inst, mock_deepseek_inst]
        
        # Fast sleep for tests
        chain.retry_engine.sleep_for_retry = AsyncMock()
        
        yield chain, mock_gemini_inst, mock_groq_inst, mock_deepseek_inst

@pytest.mark.asyncio
async def test_successful_extraction_first_provider(mock_chain):
    chain, gemini, groq, deepseek = mock_chain
    expected = DummySchema(name="test")
    gemini.extract_structured.return_value = expected
    
    result, audit = await chain.extract_with_fallback("text", DummySchema)
    
    assert result == expected
    assert audit["provider_used"] == "gemini"
    assert audit["fallback_occurred"] is False
    assert groq.extract_structured.call_count == 0

@pytest.mark.asyncio
async def test_fallback_to_second_provider_on_500(mock_chain):
    chain, gemini, groq, deepseek = mock_chain
    gemini.extract_structured.side_effect = ProviderError("Server error", status_code=500, is_retryable=False)
    expected = DummySchema(name="test")
    groq.extract_structured.return_value = expected
    
    result, audit = await chain.extract_with_fallback("text", DummySchema)
    
    assert result == expected
    assert audit["provider_used"] == "groq"
    assert audit["fallback_occurred"] is True
    assert gemini.extract_structured.call_count == 1
    assert groq.extract_structured.call_count == 1

@pytest.mark.asyncio
async def test_deep_fallback_all_fail(mock_chain):
    chain, gemini, groq, deepseek = mock_chain
    gemini.extract_structured.side_effect = ProviderError("error", is_retryable=False)
    groq.extract_structured.side_effect = ProviderError("error", is_retryable=False)
    deepseek.extract_structured.side_effect = ProviderError("error", is_retryable=False)
    
    result, audit = await chain.extract_with_fallback("text", DummySchema)
    
    assert result is None
    assert audit["provider_used"] is None
    assert len(audit["errors"]) == 3

@pytest.mark.asyncio
async def test_rate_limit_backoff(mock_chain):
    chain, gemini, groq, deepseek = mock_chain
    
    # Gemini fails with 429 twice, then succeeds
    expected = DummySchema(name="test")
    gemini.extract_structured.side_effect = [
        RateLimitError("Too fast"),
        RateLimitError("Too fast"),
        expected
    ]
    
    result, audit = await chain.extract_with_fallback("text", DummySchema)
    
    assert result == expected
    assert audit["rate_limit_events"] == 2
    assert chain.retry_engine.sleep_for_retry.call_count == 2
    
@pytest.mark.asyncio
async def test_payload_halving_on_413(mock_chain):
    chain, gemini, groq, deepseek = mock_chain
    
    expected = DummySchema(name="test")
    gemini.extract_structured.side_effect = [
        PayloadTooLargeError("Too large"),
        expected
    ]
    
    with patch("src.extraction.providers.chain.halve_payload", return_value="halved") as mock_halve:
        result, audit = await chain.extract_with_fallback("massive text", DummySchema)
        
        assert result == expected
        assert audit["payload_reduction_events"] == 1
        mock_halve.assert_called_once_with("massive text")
