import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, JSON, Integer, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.schemas import PricingModel


class Base(DeclarativeBase):
    pass


class Source(Base):
    """
    Data sources we crawl (e.g., TechCrunch, HuggingFace)
    """
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    crawl_runs: Mapped[List["CrawlRun"]] = relationship(back_populates="source")


class CrawlRun(Base):
    """
    A single execution of a crawler against a source.
    """
    __tablename__ = "crawl_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True)  # e.g., PENDING, RUNNING, COMPLETED, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped["Source"] = relationship(back_populates="crawl_runs")
    raw_documents: Mapped[List["RawDocument"]] = relationship(back_populates="crawl_run")
    extraction_runs: Mapped[List["ExtractionRun"]] = relationship(back_populates="crawl_run")


class RawDocument(Base):
    """
    Raw data (HTML/JSON) collected from a crawl.
    """
    __tablename__ = "raw_documents"
    __table_args__ = (
        UniqueConstraint('canonical_url', 'content_hash', name='uix_canonical_url_content_hash'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url: Mapped[str] = mapped_column(String)
    # Important: Indexed but NOT unique, to allow different sources to have same content, or track over time
    canonical_url: Mapped[Optional[str]] = mapped_column(String, index=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String, index=True)
    
    raw_html: Mapped[Optional[str]] = mapped_column(String)
    clean_text: Mapped[Optional[str]] = mapped_column(String)
    
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    status: Mapped[str] = mapped_column(String, index=True)  # e.g., PENDING, EXTRACTED, FAILED
    
    crawl_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("crawl_runs.id"))

    crawl_run: Mapped[Optional["CrawlRun"]] = relationship(back_populates="raw_documents")


class ExtractionRun(Base):
    """
    A single execution of the LLM extraction pipeline.
    """
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("crawl_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    model_used: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    crawl_run: Mapped[Optional["CrawlRun"]] = relationship(back_populates="extraction_runs")


# ---------------------------------------------------------
# Entity Tables (Extracted Data)
# ---------------------------------------------------------

class Startup(Base):
    __tablename__ = "startups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name: Mapped[str] = mapped_column(String, unique=True)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(String)
    website: Mapped[Optional[str]] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("raw_documents.id"))
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("extraction_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    startup_name: Mapped[str] = mapped_column(String, index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String)
    pricing_model: Mapped[Optional[PricingModel]] = mapped_column(SQLEnum(PricingModel))
    description: Mapped[Optional[str]] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("raw_documents.id"))
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("extraction_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResearchPaper(Base):
    __tablename__ = "research_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String)
    authors: Mapped[Optional[list]] = mapped_column(JSON)
    paper_url: Mapped[Optional[str]] = mapped_column(String, unique=True)
    github_url: Mapped[Optional[str]] = mapped_column(String)
    github_stars: Mapped[Optional[int]] = mapped_column(Integer)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("raw_documents.id"))
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("extraction_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[Optional[str]] = mapped_column(String)
    role_family: Mapped[Optional[str]] = mapped_column(String)
    is_remote: Mapped[Optional[bool]] = mapped_column(Boolean)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("raw_documents.id"))
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("extraction_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class News(Base):
    __tablename__ = "news"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[Optional[str]] = mapped_column(String)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[Optional[str]] = mapped_column(String)
    
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("raw_documents.id"))
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("extraction_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
