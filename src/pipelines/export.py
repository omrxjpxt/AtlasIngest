import logging
import json
import os
from sqlalchemy import select
from pydantic import HttpUrl

from src.database.connection import get_session
from src.database.models import ResearchPaper
from src.models.schemas import ResearchPaperRecord, ResearchPaperContent, Source

logger = logging.getLogger(__name__)

async def run_export(output_file: str = "data/research_papers.jsonl"):
    """
    Exports valid research papers to a JSONL file.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    logger.info(f"Exporting Research Papers to {output_file}...")
    
    count = 0
    async with get_session() as session:
        stmt = select(ResearchPaper)
        result = await session.execute(stmt)
        papers = result.scalars().all()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for paper in papers:
                try:
                    record = ResearchPaperRecord(
                        source=Source(
                            name=paper.source_name or "Unknown", 
                            url=paper.paper_url or "http://unknown"
                        ),
                        content=ResearchPaperContent(
                            title=paper.title,
                            authors=paper.authors or [],
                            paper_url=paper.paper_url,
                            github_url=paper.github_url,
                            github_stars=paper.github_stars,
                            published_date=paper.published_date
                        )
                    )
                    # Use Pydantic to dump JSON
                    f.write(record.model_dump_json() + "\n")
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to export paper {paper.id}: {e}")
                    
    logger.info(f"Exported {count} papers successfully.")
