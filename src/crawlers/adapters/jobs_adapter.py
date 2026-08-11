import logging
import json
import xml.etree.ElementTree as ET
from typing import AsyncGenerator, Tuple, Any, List
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser

from src.crawlers.engine import CrawlerEngine, CrawlRequest
from src.models.schemas import JobRecord, JobContent, Source

logger = logging.getLogger(__name__)

class JobsAdapter:
    def __init__(self, engine: CrawlerEngine):
        self.engine = engine
        self.sources = [
            ("RemoteOK", "https://remoteok.com/api?tag=ai", "json"),
            ("Remotive", "https://remotive.com/api/remote-jobs?category=software-dev&search=ai", "json"),
            ("Arbeitnow", "https://www.arbeitnow.com/api/job-board-api", "json"),
            ("Jobicy", "https://jobicy.com/api/v2/remote-jobs", "json"),
            ("WeWorkRemotely", "https://weworkremotely.com/categories/remote-programming-jobs.rss", "rss")
        ]
        
    async def fetch_and_parse_all(self) -> AsyncGenerator[Tuple[JobRecord, str], None]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        
        for name, url, format in self.sources:
            req = CrawlRequest(url=url)
            res = await self.engine.process_request(req)
            if not res.raw_html:
                logger.error(f"Failed to fetch {url}")
                continue
                
            try:
                if format == "json":
                    data = json.loads(res.raw_html)
                    records = self._parse_json(name, url, data)
                elif format == "rss":
                    records = self._parse_rss(name, url, res.raw_html)
                else:
                    records = []
                    
                for rec in records:
                    if rec.content.date and rec.content.date >= cutoff and rec.content.date <= now:
                        yield rec, rec.content.role
            except Exception as e:
                logger.error(f"Error parsing jobs from {url}: {e}")
                
    def _parse_json(self, source_name: str, url: str, data: Any) -> List[JobRecord]:
        records = []
        
        # Determine structure
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "jobs" in data: items = data["jobs"]
            elif "data" in data: items = data["data"]
            
        for item in items:
            if not isinstance(item, dict): continue
            
            # Common fields
            title = item.get("title") or item.get("position")
            company = item.get("company_name") or item.get("company")
            job_url = item.get("url") or item.get("apply_url")
            date_str = item.get("date") or item.get("publication_date") or item.get("pubDate") or item.get("created_at")
            location = item.get("location") or item.get("candidate_required_location")
            is_remote = True # Default for these boards
            
            # Skip remoteok meta tags
            if item.get("legal"): continue
            
            if not title or not company or not job_url or not date_str:
                continue
                
            try:
                if isinstance(date_str, (int, float)):
                    dt = datetime.fromtimestamp(date_str, tz=timezone.utc)
                else:
                    dt = date_parser.parse(date_str).astimezone(timezone.utc)
            except:
                continue
                
            rec = JobRecord(
                source=Source(name=source_name, url=job_url),
                content=JobContent(
                    company=company,
                    role=title,
                    date=dt,
                    is_remote=is_remote,
                    location=location,
                    role_family="Engineering"
                )
            )
            records.append(rec)
            
        return records

    def _parse_rss(self, source_name: str, url: str, xml_str: str) -> List[JobRecord]:
        records = []
        try:
            root = ET.fromstring(xml_str)
            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")
                pubDate = item.findtext("pubDate")
                
                if not title or not link or not pubDate:
                    continue
                    
                company = title.split(":")[0] if ":" in title else title
                role = title.split(":")[1].strip() if ":" in title else title
                
                try:
                    dt = date_parser.parse(pubDate).astimezone(timezone.utc)
                except:
                    continue
                    
                rec = JobRecord(
                    source=Source(name=source_name, url=link),
                    content=JobContent(
                        company=company,
                        role=role,
                        date=dt,
                        is_remote=True,
                        role_family="Engineering"
                    )
                )
                records.append(rec)
        except Exception as e:
            logger.error(f"XML Parse error: {e}")
        return records
