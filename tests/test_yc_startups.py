import pytest
import json
from src.crawlers.adapters.yc_startups import YCStartupAdapter
from src.models.schemas import StartupRecord

class MockCrawlerEngine:
    async def process_request(self, req):
        class MockResult:
            success = True
            raw_html = '''<div data-page="{&quot;props&quot;:{&quot;totalPages&quot;:1,&quot;companies&quot;:[
                {&quot;name&quot;:&quot;Computable&quot;,&quot;slug&quot;:&quot;computable&quot;,&quot;team_size&quot;:2},
                {&quot;name&quot;:&quot;MissingEmp&quot;,&quot;slug&quot;:&quot;missing-emp&quot;,&quot;team_size&quot;:null},
                {&quot;name&quot;:&quot;InvalidEmp&quot;,&quot;slug&quot;:&quot;invalid-emp&quot;,&quot;team_size&quot;:&quot;abc&quot;},
                {&quot;name&quot;:&quot;MissingSlug&quot;}
            ]}}"></div>'''
            error = None
        return MockResult()
        
@pytest.mark.asyncio
async def test_yc_startup_adapter():
    engine = MockCrawlerEngine()
    adapter = YCStartupAdapter(engine=engine)
    
    records = []
    async for record in adapter.fetch_and_parse_all(target_count=10):
        records.append(record)
        
    assert len(records) == 3
    
    r1 = records[0]
    assert r1.content.entityName == "Computable"
    assert r1.content.data.employeeCount == 2
    assert str(r1.source.url) == "https://www.ycombinator.com/companies/computable"
    
    r2 = records[1]
    assert r2.content.entityName == "MissingEmp"
    assert r2.content.data.employeeCount is None
    
    r3 = records[2]
    assert r3.content.entityName == "InvalidEmp"
    assert r3.content.data.employeeCount is None
