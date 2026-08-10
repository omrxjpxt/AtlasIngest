from abc import ABC, abstractmethod
from typing import List
from src.crawlers.models import CrawlRequest, CrawlResult
from src.crawlers.policies import SourcePolicy

class SourceAdapter(ABC):
    def __init__(self, policy: SourcePolicy):
        self.policy = policy

    @abstractmethod
    async def discover(self) -> List[CrawlRequest]:
        """
        Discovers URLs to crawl and returns a list of CrawlRequests.
        """
        pass

    @abstractmethod
    async def parse(self, result: CrawlResult):
        """
        Parses the raw HTML result into structured data.
        """
        pass
