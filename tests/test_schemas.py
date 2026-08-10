import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.models.schemas import (
    StartupRecord,
    StartupContent,
    StartupContentData,
    ProductRecord,
    ProductContent,
    PricingModel,
    ResearchPaperRecord,
    ResearchPaperContent,
    JobRecord,
    JobContent,
    NewsRecord,
    Source,
    RecordType,
)

def test_valid_startup_record():
    source = Source(name="TechCrunch", url="https://techcrunch.com/article")
    data = StartupContentData(employeeCount=50)
    content = StartupContent(entityName="Anthropic", data=data)
    
    record = StartupRecord(source=source, content=content)
    
    assert record.schemaVersion == "1.0"
    assert record.recordType == RecordType.STARTUP
    assert record.content.entityName == "Anthropic"
    assert record.content.data.employeeCount == 50
    assert record.collectedAt is not None

def test_negative_employee_count_rejected():
    with pytest.raises(ValidationError) as exc_info:
        StartupContentData(employeeCount=-5)
    
    assert "employeeCount cannot be negative" in str(exc_info.value)

def test_invalid_url_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Source(name="Invalid", url="not-a-url")
        
    assert "url" in str(exc_info.value)

def test_valid_product_record():
    source = Source(name="ProductHunt", url="https://producthunt.com/posts/claude")
    content = ProductContent(startupName="Anthropic", pricingModel=PricingModel.FREEMIUM)
    
    record = ProductRecord(source=source, content=content)
    
    assert record.recordType == RecordType.PRODUCT
    assert record.content.pricingModel == PricingModel.FREEMIUM

def test_valid_research_paper_record():
    source = Source(name="Arxiv", url="https://arxiv.org/abs/2301.00001")
    content = ResearchPaperContent(
        title="Scaling Laws",
        authors=["Alice", "Bob"],
        github_stars=1000
    )
    
    record = ResearchPaperRecord(source=source, content=content)
    
    assert record.recordType == RecordType.RESEARCH_PAPER
    assert record.content.github_stars == 1000
    assert len(record.content.authors) == 2

def test_negative_github_stars_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ResearchPaperContent(
            title="Cool Paper",
            github_stars=-10
        )
        
    assert "github_stars cannot be negative" in str(exc_info.value)

def test_valid_job_record():
    source = Source(name="YCW", url="https://ycombinator.com/jobs/123")
    dt = datetime(2023, 10, 1, tzinfo=timezone.utc)
    content = JobContent(
        company="OpenAI",
        is_remote=True,
        role_family="Engineering",
        date=dt
    )
    
    record = JobRecord(source=source, content=content)
    
    assert record.recordType == RecordType.JOB
    assert record.content.is_remote is True
    assert record.content.date == dt

def test_valid_news_record():
    source = Source(name="AI News", url="https://ainews.com/post")
    dt = datetime(2023, 10, 1, tzinfo=timezone.utc)
    
    record = NewsRecord(
        source=source,
        title="OpenAI releases new model",
        url="https://ainews.com/post",
        published_date=dt
    )
    
    assert record.recordType == RecordType.NEWS
    assert record.title == "OpenAI releases new model"
    assert record.published_date == dt

def test_invalid_record_type_rejected():
    source = Source(name="Test", url="https://test.com")
    content = StartupContent(entityName="Test", data=StartupContentData())
    
    with pytest.raises(ValidationError) as exc_info:
        # Trying to pass PRODUCT to a STARTUP record
        StartupRecord(source=source, content=content, recordType=RecordType.PRODUCT)
        
    assert "recordType must be STARTUP" in str(exc_info.value)
