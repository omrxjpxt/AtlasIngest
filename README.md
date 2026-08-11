# IntelligenceForge

IntelligenceForge is an automated, scalable data aggregation pipeline designed to discover, extract, normalize, and store large volumes of structured records. It specializes in academic research papers (arXiv), AI startups (Y Combinator), and AI products (Futurepedia).

## Architecture

The system utilizes an asynchronous ingestion architecture:
- **CrawlerEngine**: Leverages `asyncio` and `aiohttp` for robust, high-concurrency network collection with strict rate-limit handling and smart retries (429 handling, exponential backoff).
- **PostgreSQL**: Stores both `raw_documents` (for auditing and LLM fallback) and structured entities (`research_papers`, `startups`, `products`).
- **Entity Normalization**: Deterministically deduplicates entity records before insertion.
- **SQLAlchemy 2.0 / asyncpg**: Provides typed, scalable database access.

*For full details on the scale strategy, deduplication, 413/429 handling, and anti-bot measures, please see [architecture.pdf](architecture.pdf).*

## Completed Phases

- **Phase 1: Architecture Setup** - Database schema, raw document persistence, and pipeline interfaces.
- **Phase 2: Academic Papers (arXiv)** - High-volume extraction via Atom XML parsing.
- **Phase 3: Real Data Verification** - Full audit, testing, and production export pipelines.
- **Phase 4: Startups & Products** - Real-data extraction from Y Combinator and Futurepedia.
- **Phase 5 (Planned)**: LLM Fallback extraction for unstructured data.

## Data Quality Guarantees

- **No Hallucinated Data**: All fields are deterministically extracted from reliable origins. Missing data correctly produces `null` rather than estimated values.
- **Strict Provenance**: Every record contains the original `source.url` and `source.name` for immediate auditing.
- **Verified Extraction Constraints**: The pipeline enforces schema validation, dropping corrupt or incomplete records (e.g. products without valid providers).

## Prerequisites

- Python 3.10+
- PostgreSQL 14+
- (Optional) `fpdf2` for regenerating the architecture document.

## Setup

1. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Environment Variables:**
   ```bash
   export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/intelligence_forge"
   export CRAWLER_VERIFY_SSL=true
   ```

## Commands

Run the CLI for data collection:

```bash
# Research Papers
python -m src.main papers --target 1200

# Startups (YC)
python -m src.main startups --target 1200

# Products (Futurepedia)
python -m src.main products --target 1200

# Run Data Audit
python -m src.main audit

# Export to JSONL
python -m src.main export --format jsonl
```

## Data Outputs

Output data is exported into the `data/` directory.

- `research_papers.jsonl` / `research_papers.csv` (1300 records)
- `startups.jsonl` / `startups.csv` (1225 records)
- `products.jsonl` / `products.csv` (86 records)

*Note: CSV conversions can be executed via `python convert_to_csv.py` after JSONL generation.*

## Test Results
- **Pytest**: 35/35 passing. Run via `python -m pytest tests/ -v`.
- **Smoke Tests**: 25/25 verified successfully for each target domain before production scaling.

## Entity Resolution

The system uses deterministic and source-verified normalization rather than complex fuzzy entity resolution. Canonicalization is handled as follows:

- **Startups & Jobs:** The pipeline trusts the authoritative source directory (e.g., Y Combinator for Startups, or the job board for Jobs) as the canonical representation. It extracts the raw name provided by the source, stores it as the canonical name, and uses `source_verified` tracking.
- **Products:** The pipeline performs strict deterministic string normalization on product owner strings using NFKD unicode decomposition, lowercasing, and removal of legal suffixes (inc, llc, corp) and whitespace. The system relies on this normalized string (`normalized_exact`) for mapping products to their owning startup. The original raw strings are not persisted beyond ingestion, and thus the mapping log reflects the post-normalization state as the proven mapping.

*Sophisticated fuzzy matching or LLM-based entity resolution is intentionally excluded to strictly comply with the rule preventing hallucinated or assumed relationships.*

## Limitations
- **Dynamic Content**: Extraction heavily relies on standard HTML or predictable structured JSON payloads (e.g. `data-page`). For example, Futurepedia's pagination uses JavaScript routing which restricts our static crawler to only 86 explicit products before requiring full JS rendering. 
- **Strict Data Validation Rules**: We strictly avoid hallucinated data. If a product lacks explicit pricing or an explicit owner, we reject it (e.g. `PRICING_UNRESOLVED`, `OWNER_UNRESOLVED`) rather than pollute the database with LLM guesses or assumed defaults. Future upgrades plan to leverage LLMs (Phase 5) to robustly process unstructured pages while maintaining data integrity.
