class IntelligenceForgeError(Exception):
    """Base exception for all IntelligenceForge errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ConfigurationError(IntelligenceForgeError):
    """Raised when there is an issue with application configuration or environment variables."""
    pass

class DatabaseError(IntelligenceForgeError):
    """Raised when a database operation fails."""
    pass

class CrawlerError(IntelligenceForgeError):
    """Raised when a crawler encounters an error fetching or parsing data."""
    pass

class ExtractionError(IntelligenceForgeError):
    """Raised when LLM extraction fails or produces invalid output."""
    pass

class SchemaValidationError(IntelligenceForgeError):
    """Raised when data fails validation against our internal schemas."""
    pass

class ResolutionError(IntelligenceForgeError):
    """Raised when entity resolution or deduplication fails."""
    pass

class EnrichmentError(IntelligenceForgeError):
    """Raised when an enrichment step (e.g. GitHub API, Google Sheets) fails."""
    pass
