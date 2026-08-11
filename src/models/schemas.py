from enum import Enum
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, HttpUrl, Field, ConfigDict, field_validator

# ---------------------------------------------------------
# Enums
# ---------------------------------------------------------

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"

class RecordType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"


# ---------------------------------------------------------
# Reusable Nested Models
# ---------------------------------------------------------

class Source(BaseModel):
    name: str = Field(..., description="The name of the source (e.g., 'TechCrunch', 'HuggingFace')")
    url: HttpUrl = Field(..., description="The URL of the source or specific page")

class CollectedMetadata(BaseModel):
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = Field(default="1.0")


# ---------------------------------------------------------
# Entity Records
# ---------------------------------------------------------

class BaseRecord(BaseModel):
    """Base class for all entity records."""
    schemaVersion: str = Field(default="1.0")
    recordType: RecordType
    source: Source
    collectedAt: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("schemaVersion")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError("schemaVersion must be '1.0'")
        return v

# --- Startup ---

class StartupContentData(BaseModel):
    employeeCount: Optional[int] = None
    
    @field_validator("employeeCount")
    @classmethod
    def validate_employee_count(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("employeeCount cannot be negative")
        return v

class StartupContent(BaseModel):
    entityName: str
    data: StartupContentData = Field(default_factory=StartupContentData)

class StartupRecord(BaseRecord):
    recordType: RecordType = Field(default=RecordType.STARTUP)
    content: StartupContent
    
    @field_validator("recordType")
    @classmethod
    def validate_record_type(cls, v: RecordType) -> RecordType:
        if v != RecordType.STARTUP:
            raise ValueError(f"recordType must be {RecordType.STARTUP}")
        return v


# --- Product ---

class ProductContent(BaseModel):
    startupName: str
    pricingModel: Optional[PricingModel] = None

class ProductRecord(BaseRecord):
    recordType: RecordType = Field(default=RecordType.PRODUCT)
    content: ProductContent
    
    @field_validator("recordType")
    @classmethod
    def validate_record_type(cls, v: RecordType) -> RecordType:
        if v != RecordType.PRODUCT:
            raise ValueError(f"recordType must be {RecordType.PRODUCT}")
        return v


# --- Research Paper ---

class ResearchPaperContent(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    paper_url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    github_stars: Optional[int] = None
    published_date: Optional[datetime] = None

    @field_validator("github_stars")
    @classmethod
    def validate_github_stars(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("github_stars cannot be negative")
        return v

class ResearchPaperRecord(BaseRecord):
    recordType: RecordType = Field(default=RecordType.RESEARCH_PAPER)
    content: ResearchPaperContent
    
    @field_validator("recordType")
    @classmethod
    def validate_record_type(cls, v: RecordType) -> RecordType:
        if v != RecordType.RESEARCH_PAPER:
            raise ValueError(f"recordType must be {RecordType.RESEARCH_PAPER}")
        return v


# --- Job ---

class JobContent(BaseModel):
    company: str
    role: str
    date: Optional[datetime] = None
    is_remote: Optional[bool] = None
    role_family: Optional[str] = None
    location: Optional[str] = None

class JobRecord(BaseRecord):
    recordType: RecordType = Field(default=RecordType.JOB)
    content: JobContent
    
    @field_validator("recordType")
    @classmethod
    def validate_record_type(cls, v: RecordType) -> RecordType:
        if v != RecordType.JOB:
            raise ValueError(f"recordType must be {RecordType.JOB}")
        return v


# --- News ---

class NewsContent(BaseModel):
    title: str
    published_date: Optional[datetime] = None
    summary: Optional[str] = None

class NewsRecord(BaseRecord):
    recordType: RecordType = Field(default=RecordType.NEWS)
    title: str
    url: HttpUrl
    published_date: Optional[datetime] = None
    summary: Optional[str] = None
    
    @field_validator("recordType")
    @classmethod
    def validate_record_type(cls, v: RecordType) -> RecordType:
        if v != RecordType.NEWS:
            raise ValueError(f"recordType must be {RecordType.NEWS}")
        return v
