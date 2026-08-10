import pytest
import asyncio
from aiohttp import web
from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.database.connection import init_db, close_db, get_session
from src.database.models import RawDocument, CrawlRun
from sqlalchemy import select, delete

# Setup a simple local server
async def handle_success(request):
    return web.Response(text="<html>Success Integration</html>", content_type='text/html')

async def start_local_server(port=8080):
    app = web.Application()
    app.add_routes([web.get('/success', handle_success)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    return runner

@pytest.mark.asyncio
@pytest.mark.integration
async def test_crawler_integration():
    # Attempt to init DB, if it fails, skip the test
    try:
        await init_db()
    except Exception as e:
        pytest.skip(f"Database not available for integration test: {e}")

    # Clean up any previous test runs from RawDocument
    async with get_session() as session:
        await session.execute(delete(RawDocument).where(RawDocument.source_url.like('%localhost:8080%')))
        await session.commit()
    
    server_runner = await start_local_server(8080)
    
    engine = CrawlerEngine(max_retries=1)
    await engine.start()
    
    # Process the same request twice to test duplicate handling
    req1 = CrawlRequest(url="http://localhost:8080/success")
    req2 = CrawlRequest(url="http://localhost:8080/success")
    
    results = await engine.process_batch([req1, req2])
    
    # Both should be marked as success in the crawler result layer
    assert results[0].success is True
    assert results[1].success is True
    
    # Check Database for how many were saved
    async with get_session() as session:
        stmt = select(RawDocument).where(RawDocument.source_url == "http://localhost:8080/success")
        result = await session.execute(stmt)
        docs = result.scalars().all()
        
        # Only one should have been inserted due to the UniqueConstraint on canonical_url + content_hash
        assert len(docs) == 1
        assert docs[0].raw_html == "<html>Success Integration</html>"
        
    await engine.close()
    await server_runner.cleanup()
    await close_db()
