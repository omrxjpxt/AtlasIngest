from typing import Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
import uuid

class CrawlRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[bytes] = None
    source_id: Optional[uuid.UUID] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    priority: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CrawlResult(BaseModel):
    requested_url: str
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    raw_html: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: Optional[int] = None
    success: bool = False
    error: Optional[str] = None
    retry_count: int = 0
    content_hash: Optional[str] = None
