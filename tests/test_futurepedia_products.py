import pytest
from src.crawlers.adapters.futurepedia_products import FuturepediaProductAdapter
from src.models.schemas import PricingModel

class MockCrawlerEngine:
    async def process_request(self, req):
        class MockResult:
            success = True
            raw_html = ""
            error = None
        
        result = MockResult()
        if req.url == "https://www.futurepedia.io/ai-tools":
            result.raw_html = '<a href="/ai-tools/test-cat">Test Cat</a>'
        elif req.url == "https://www.futurepedia.io/ai-tools/test-cat":
            result.raw_html = '<a href="/tool/test-tool">Test Tool</a>'
        elif req.url == "https://www.futurepedia.io/tool/test-tool":
            result.raw_html = '''
            <html>
            <script type="application/ld+json">
            {"@type": "SoftwareApplication", "name": "Test Tool", "author": {"@type": "Organization", "name": "Test Provider"}}
            </script>
            <div>Pricing Model: </span><div>Freemium</div></div>
            </html>
            '''
        return result

@pytest.mark.asyncio
async def test_futurepedia_product_adapter():
    engine = MockCrawlerEngine()
    adapter = FuturepediaProductAdapter(engine=engine)
    
    records = []
    async for record, product_name in adapter.fetch_and_parse_all(target_count=10):
        records.append((record, product_name))
        
    assert len(records) == 1
    r, product_name = records[0]
    assert r.content.startupName == "Test Provider"
    assert r.content.pricingModel == PricingModel.FREEMIUM
    assert str(r.source.url) == "https://www.futurepedia.io/tool/test-tool"
    assert product_name == "Test Tool"

def test_normalize_pricing():
    adapter = FuturepediaProductAdapter(engine=None)
    assert adapter._normalize_pricing("Free") == PricingModel.FREE
    assert adapter._normalize_pricing("Freemium") == PricingModel.FREEMIUM
    assert adapter._normalize_pricing("Paid") == PricingModel.PAID
    assert adapter._normalize_pricing("Free + Paid") == PricingModel.FREEMIUM
    assert adapter._normalize_pricing("Enterprise") == PricingModel.ENTERPRISE
    assert adapter._normalize_pricing("Unknown") is None
