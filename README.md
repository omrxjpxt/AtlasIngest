# IntelligenceForge

IntelligenceForge is a production-grade data intelligence pipeline designed to ingest, process, and enrich AI ecosystem data from various web sources (Startups, Products, Research Papers, Jobs, and News).

## Architecture & Scope

This project will eventually perform:
`Source → Async Crawling → Raw Data → Cleaning → LLM Extraction → Validation → Entity Resolution → Enrichment → PostgreSQL → Google Sheets`

### Phase 1 & 2 (Current Scope)
Phase 1 established the clean project foundation, including:
- Strong typed Pydantic schemas for entities
- Database schema (SQLAlchemy 2.x + asyncpg)
- Configuration and Structured Logging

Phase 2 established the Core Async Crawling Engine:
- Robust `aiohttp` based async HTTP client with connection pooling
- Configurable concurrency controls (global and per-host limits)
- Exponential backoff with jitter for retries
- URL canonicalization and SHA-256 content hashing for duplicate detection
- PostgreSQL persistence of `RawDocument` with integrity conflict handling
- Abstract `SourceAdapter` and `SourcePolicy` foundation

**Note:** Production source adapters (scraping specific websites) and LLM extraction are deliberately *not* implemented yet. There is no mock/fake data generation.

## Project Structure

```
intelligence-forge/
├── src/
│   ├── config/       # Pydantic-based settings management
│   ├── models/       # Pydantic schemas and Enums
│   ├── database/     # SQLAlchemy models and connection lifecycle
│   ├── core/         # Structured logging and exceptions
│   ├── crawlers/     # (Phase 2+) Async crawling logic
│   ├── extraction/   # (Phase 2+) LLM extraction
│   ├── resolution/   # (Phase 2+) Entity resolution/deduplication
│   ├── enrichment/   # (Phase 2+) GitHub/Sheets integration
│   ├── storage/      # (Phase 2+) Export mechanisms
│   └── main.py       # Application entrypoint
├── tests/            # Pytest test suite
├── .env.example      # Example environment variables
└── pyproject.toml    # Project metadata
```

## Setup & Execution

### Requirements
- Python 3.11+
- PostgreSQL

### Installation
1. Clone the repository and navigate into it.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. **Set Configuration**: Create a `.env` file from the example (if provided) and fill in your details:
   ```bash
   cp .env.example .env
   # Ensure DATABASE_URL is set, e.g., DATABASE_URL="postgresql+asyncpg://localhost/intelligence_forge"
   ```

### macOS Troubleshooting: SSL Certificate Verify Failed

If you are running Python on macOS (especially the official installer from Python.org) and encounter `[SSL: CERTIFICATE_VERIFY_FAILED]` when running the crawlers:

macOS Python does not use the system's root certificates by default. To fix this, run the command included with your Python installation:
```bash
/Applications/Python\ 3.10/Install\ Certificates.command
```
*(Replace `3.10` with your actual Python version).*

Alternatively, if you installed via Homebrew, ensure the `certifi` package is up to date:
```bash
pip install --upgrade certifi
```

If you absolutely must bypass SSL verification for local development (not recommended), you can set `CRAWLER_VERIFY_SSL=false` in your `.env` file. This will log explicit warnings during execution.

## Running the Application
To run the entrypoint, which verifies configuration, sets up logging, and initializes the database tables (requires PostgreSQL):
```bash
python -m src.main
```

To run a test crawl using the Phase 2 engine:
```bash
python -m src.main crawl --url https://example.com
```

### Running Tests
Unit tests do not require a live PostgreSQL instance or internet connection (they are mocked).
```bash
pytest tests/ -v
```
