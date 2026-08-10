from typing import Optional
from pydantic import BaseModel

class SourcePolicy(BaseModel):
    source_name: str
    max_concurrency: int = 5
    request_delay: float = 0.0
    respect_robots: bool = True
    use_browser: bool = False
    max_retries: int = 3
    timeout: int = 30
