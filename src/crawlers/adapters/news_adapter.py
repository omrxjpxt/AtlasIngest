import logging
import xml.etree.ElementTree as ET
from typing import AsyncGenerator, Tuple, List
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser

from src.crawlers.engine import CrawlerEngine, CrawlRequest
from src.models.schemas import NewsRecord, NewsContent, Source

logger = logging.getLogger(__name__)

class NewsAdapter:
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.sources = [
            ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
            ("VentureBeat", "https://venturebeat.com/category/ai/feed/"),
            ("Wired", "https://www.wired.com/feed/tag/ai/latest/rss"),
            ("TheVerge", "https://www.theverge.com/rss/artificial-intelligence/index.xml"),
            ("AINews", "https://www.artificialintelligence-news.com/feed/")
        ]
        
    async def fetch_and_parse_all(self) -> AsyncGenerator[Tuple[NewsRecord, str], None]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        
        for name, url in self.sources:
            req = CrawlRequest(url=url)
            res = await self.engine.process_request(req)
            if not res.raw_html:
                logger.error(f"Failed to fetch {url}")
                continue
                
            try:
                records = self._parse_rss(name, url, res.raw_html)
                for rec in records:
                    if rec.published_date and rec.published_date >= cutoff and rec.published_date <= now:
                        yield rec, rec.title
            except Exception as e:
                logger.error(f"Error parsing news from {url}: {e}")

    def _parse_rss(self, source_name: str, source_url: str, xml_str: str) -> List[NewsRecord]:
        records = []
        try:
            root = ET.fromstring(xml_str)
            # Find items in RSS or Atom
            items = root.findall(".//item")
            if not items:
                # Try Atom format (e.g. The Verge)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall(".//atom:entry", ns)
                
            for item in items:
                # RSS
                title = item.findtext("title")
                link = item.findtext("link")
                pubDate = item.findtext("pubDate")
                summary = item.findtext("description")
                
                # Atom fallback
                if not title:
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    t = item.find("atom:title", ns)
                    title = t.text if t is not None else None
                    l = item.find("atom:link", ns)
                    link = l.attrib.get("href") if l is not None else None
                    p = item.find("atom:published", ns)
                    if p is None: p = item.find("atom:updated", ns)
                    pubDate = p.text if p is not None else None
                    s = item.find("atom:summary", ns)
                    if s is None: s = item.find("atom:content", ns)
                    summary = s.text if s is not None else ""
                
                if not title or not link or not pubDate:
                    continue
                    
                try:
                    dt = date_parser.parse(pubDate).astimezone(timezone.utc)
                except:
                    continue
                    
                rec = NewsRecord(
                    source=Source(name=source_name, url=link),
                    title=title,
                    url=link,
                    published_date=dt,
                    summary=summary
                )
                records.append(rec)
        except Exception as e:
            logger.error(f"XML Parse error: {e}")
            
        return records
