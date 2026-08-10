# IntelligenceForge

IntelligenceForge is a production-grade data intelligence pipeline designed to ingest, process, and enrich AI ecosystem data from various web sources (Startups, Products, Research Papers, Jobs, and News).

## Architecture & Scope

This project will eventually perform:
`Source → Async Crawling → Raw Data → Cleaning → LLM Extraction → Validation → Entity Resolution → Enrichment → PostgreSQL → Google Sheets`

### Phase 1 (Current Scope)
Phase 1 establishes the clean project foundation, including:
- Strong typed Pydantic schemas for entities
- Database schema (SQLAlchemy 2.x + asyncpg)
- Configuration and Structured Logging
- Error exception hierarchy
- Initial testing suite

**Note:** Crawling, LLM extraction, and API integrations are deliberately *not* implemented in Phase 1. There is no mock/fake data generation.

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
4. Copy the environment variables:
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` to match your local PostgreSQL credentials.*

### Running the Application (Phase 1)
To run the entrypoint, which verifies configuration, sets up logging, and initializes the database tables (requires PostgreSQL):
```bash
python -m src.main
```

### Running Tests
Unit tests do not require a live PostgreSQL instance.
```bash
pytest tests/ -v
```
