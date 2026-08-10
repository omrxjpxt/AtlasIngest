import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.crawlers.adapters.arxiv import ArxivAdapter
from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlResult

@pytest.fixture
def mock_engine():
    engine = MagicMock(spec=CrawlerEngine)
    engine.fetch_with_retry = AsyncMock()
    return engine

@pytest.fixture
def arxiv_adapter(mock_engine):
    return ArxivAdapter(engine=mock_engine)

def test_extract_arxiv_id(arxiv_adapter):
    assert arxiv_adapter._extract_arxiv_id("http://arxiv.org/abs/2608.07468v1") == "2608.07468"
    assert arxiv_adapter._extract_arxiv_id("https://arxiv.org/abs/2106.09685") == "2106.09685"
    assert arxiv_adapter._extract_arxiv_id("invalid") == ""

def test_parse_atom_response_success(arxiv_adapter):
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2608.07468v1</id>
        <published>2026-08-07T18:00:00Z</published>
        <title>SimWAM: A Simple World Action Model</title>
        <author><name>Zongchuang Zhao</name></author>
        <author><name>Xin Zhou</name></author>
      </entry>
    </feed>
    """
    records = arxiv_adapter.parse_atom_response(xml_data, "http://test")
    assert len(records) == 1
    
    record, arxiv_id = records[0]
    assert arxiv_id == "2608.07468"
    assert record.content.title == "SimWAM: A Simple World Action Model"
    assert record.content.authors == ["Zongchuang Zhao", "Xin Zhou"]
    assert str(record.content.paper_url) == "https://arxiv.org/abs/2608.07468"
    assert record.content.published_date.year == 2026

def test_parse_atom_response_malformed(arxiv_adapter):
    # Missing title and ID
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <published>2026-08-07T18:00:00Z</published>
      </entry>
    </feed>
    """
    records = arxiv_adapter.parse_atom_response(xml_data, "http://test")
    assert len(records) == 0

@pytest.mark.asyncio
async def test_fetch_batch(arxiv_adapter, mock_engine):
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2608.07468v1</id>
        <title>Test Title</title>
      </entry>
    </feed>"""
    
    mock_engine.fetch_with_retry.return_value = CrawlResult(
        requested_url="http://test",
        success=True,
        raw_html=xml_data
    )
    
    records = await arxiv_adapter.fetch_batch(0)
    assert len(records) == 1
    assert records[0][1] == "2608.07468"
