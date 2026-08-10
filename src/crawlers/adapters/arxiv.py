import logging
from typing import List, AsyncGenerator
from lxml import etree
import re
from datetime import datetime, timezone

from src.crawlers.engine import CrawlerEngine
from src.crawlers.models import CrawlRequest
from src.models.schemas import ResearchPaperRecord, ResearchPaperContent, Source

logger = logging.getLogger(__name__)

class ArxivAdapter:
    """
    Adapter for discovering and fetching research papers from the arXiv API.
    Uses the Phase 2 crawler engine for resilient HTTP fetching.
    """
    def __init__(self, engine: CrawlerEngine, batch_size: int = 100):
        self.engine = engine
        self.batch_size = batch_size
        self.base_url = "http://export.arxiv.org/api/query"
        self.categories = ["cs.AI", "cs.LG", "cs.CL"]
        self.namespace = {"atom": "http://www.w3.org/2005/Atom"}
        
    def _build_query_url(self, offset: int) -> str:
        # Build category query: cat:cs.AI+OR+cat:cs.LG...
        cat_query = "+OR+".join([f"cat:{c}" for c in self.categories])
        url = f"{self.base_url}?search_query={cat_query}&sortBy=submittedDate&sortOrder=descending&start={offset}&max_results={self.batch_size}"
        return url
        
    def _parse_published_date(self, date_str: str) -> datetime:
        try:
            # Parse ISO 8601 from Atom XML, e.g. "2024-05-23T18:00:00Z"
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str)
        except Exception:
            return datetime.now(timezone.utc)

    def _extract_arxiv_id(self, entry_id: str) -> str:
        # e.g. http://arxiv.org/abs/2608.07468v1 -> 2608.07468
        match = re.search(r'/abs/(\d+\.\d+)', entry_id)
        if match:
            return match.group(1)
        return ""

    def parse_atom_response(self, raw_xml: str, api_url: str) -> List[tuple[ResearchPaperRecord, str]]:
        """
        Parses the Atom XML returned by arXiv and yields a list of 
        (ResearchPaperRecord, arxiv_id).
        """
        records = []
        try:
            root = etree.fromstring(raw_xml.encode('utf-8'))
            entries = root.findall("atom:entry", namespaces=self.namespace)
            
            for entry in entries:
                # Title
                title_elem = entry.find("atom:title", namespaces=self.namespace)
                title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None and title_elem.text else ""
                
                # Authors
                author_elems = entry.findall("atom:author/atom:name", namespaces=self.namespace)
                authors = [a.text.strip() for a in author_elems if a.text]
                
                # Published Date
                published_elem = entry.find("atom:published", namespaces=self.namespace)
                published_date = None
                if published_elem is not None and published_elem.text:
                    published_date = self._parse_published_date(published_elem.text)
                    
                # Paper URL & ID
                id_elem = entry.find("atom:id", namespaces=self.namespace)
                entry_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                
                # ArXiv prefers versionless URLs for canonical reference where possible
                arxiv_id = self._extract_arxiv_id(entry_id)
                paper_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else entry_id
                
                if not title or not arxiv_id:
                    # Skip malformed entries without enough identity
                    continue
                    
                record = ResearchPaperRecord(
                    source=Source(name="arXiv API", url=api_url),
                    content=ResearchPaperContent(
                        title=title,
                        authors=authors,
                        paper_url=paper_url,
                        published_date=published_date
                    )
                )
                records.append((record, arxiv_id))
                
        except Exception as e:
            logger.error(f"Failed to parse arXiv Atom XML: {e}")
            
        return records

    async def fetch_batch(self, offset: int) -> List[tuple[ResearchPaperRecord, str]]:
        """
        Fetches a batch of papers starting from `offset`.
        Returns a list of (ResearchPaperRecord, arxiv_id).
        """
        url = self._build_query_url(offset)
        req = CrawlRequest(url=url)
        
        # Use CrawlerEngine to fetch with retry and concurrency control
        result = await self.engine.fetch_with_retry(req)
        
        if result.success and result.raw_html:
            return self.parse_atom_response(result.raw_html, api_url=url)
        else:
            logger.error(f"Failed to fetch arXiv batch at offset {offset}: {result.error}")
            return []
