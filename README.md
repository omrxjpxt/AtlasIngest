# AtlasIngest

AtlasIngest is an asynchronous, source-driven data ingestion and normalization pipeline for collecting, validating, and exporting structured intelligence from multiple domains. The system is designed around deterministic extraction, strict schema validation, and explicit source provenance to produce auditable datasets suitable for downstream analytics and AI workflows.

## What It Does

The pipeline currently ingests structured intelligence across five distinct data domains:
- **Research Papers**: Extracts academic publications and their associated metadata.
- **AI Startups**: Collects company profiles, employee counts, and foundational startup information.
- **AI Products**: Aggregates AI software tools, pricing models, and product-to-startup relationships.
- **Jobs**: Identifies remote AI and engineering roles published within the last 24 hours.
- **News**: Monitors high-signal AI news articles published within the last 24 hours.

For each domain, the pipeline orchestrates network collection from authoritative sources, normalizes the raw documents into strict database schemas, deterministically validates required fields, explicitly preserves source provenance, and ultimately exports the datasets into structured formats (JSONL/CSV).

## Architecture

AtlasIngest is built on a scalable, asynchronous Python architecture:
- **Asynchronous Collection**: Leverages `asyncio` and `aiohttp` to perform highly concurrent HTTP requests, bounded by per-host and global concurrency limits to respect source infrastructure.
- **Source-Specific Adapters**: Encapsulates unique parsing logic (JSON APIs, XML/RSS feeds, HTML) into isolated crawler adapters.
- **Parsing & Normalization**: Maps unstructured and semi-structured payloads into strict Pydantic schemas before persistence.
- **Deterministic Validation**: Drops incomplete or malformed records at the boundary (e.g., rejecting missing URLs or unresolvable pricing) rather than permitting data corruption.
- **PostgreSQL Persistence**: Uses SQLAlchemy 2.0 with `asyncpg` for non-blocking, typed database interactions.
- **Raw Document Persistence**: Stores original payload data (where applicable) alongside structured entity records to support future auditing and LLM-assisted re-extraction.
- **Export Pipeline**: Streams validated records from the database into transportable data formats.
- **Resilience**: Implements automatic exponential backoff, rate-limit awareness (429 handling), and network retry logic natively within the crawler engine.

For comprehensive architectural design details, see [architecture.pdf](architecture.pdf).

## Data Sources

| Domain | Source | Record Type | Output Format |
|---|---|---|---|
| Research Papers | arXiv | XML (Atom) | JSONL / CSV |
| AI Startups | Y Combinator | JSON API | JSONL / CSV |
| AI Products | Futurepedia, AIFOXX, AITopTools | HTML / JSON | JSONL / CSV |
| Jobs | RemoteOK, Remotive, Arbeitnow, WeWorkRemotely, Jobicy | JSON API / RSS | JSONL / CSV |
| News | TechCrunch, VentureBeat, Wired, The Verge, AI News | RSS / Atom | JSONL / CSV |

## Data Integrity & Provenance

The system enforces strict engineering guarantees to prevent dataset contamination:
- **Deterministic Extraction**: Values are explicitly extracted from known, reliable payload locations.
- **Schema Validation**: All records pass through strict Pydantic models; missing or invalid critical fields (e.g., negative employee counts, unresolvable pricing) result in explicit rejection.
- **Source Provenance**: Every record permanently retains its canonical `source.url` and `source.name`.
- **No Fabrication**: The system explicitly forbids the generation, inference, or hallucination of missing data. If a value is unresolvable from the source, it is either stored as `null` (if optional) or the record is discarded entirely.
- **Deterministic Normalization**: Key entities undergo transparent, replicable normalization (e.g., NFKD unicode decomposition, lowercasing, suffix stripping) prior to deduplication.

## Entity Resolution

The pipeline resolves entities using deterministic, rule-based canonicalization. It distinguishes between:
1. **Authoritative-Source Canonicalization**: For Startups and Jobs, the system defers to the authoritative origin (e.g., Y Combinator). The original name provided by the source is extracted, preserved, and stored as the canonical entity representation (`source_verified`).
2. **Deterministic Normalization**: For Products, the system normalizes owning company names using Unicode decomposition, lowercasing, and removal of common legal suffixes (e.g., "inc", "corp") and whitespace (`normalized_exact`).
3. **Product-to-Startup Mapping**: Products are associated with startups via the deterministically normalized owner string.

*Note: Fuzzy matching and LLM-based entity resolution are intentionally excluded. The architecture prioritizes deterministic, auditable relationships over speculative or assumed matches.*

## Project Structure

```
.
├── README.md
├── architecture.pdf
├── convert_to_csv.py
├── data/
├── generate_mapping_log.py
├── generate_pdf.py
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── config/
│   ├── crawlers/
│   ├── database/
│   ├── models/
│   ├── pipelines/
│   └── main.py
└── tests/
```

## Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/omrxjpxt/AtlasIngest.git
   cd AtlasIngest
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables:**
   Create a `.env` file and define your database connection:
   ```bash
   DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/atlas_ingest"
   ```

6. **Run the pipeline:**
   ```bash
   python -m src.main papers
   ```

## Usage

The system exposes a unified CLI for managing the lifecycle of the data.

**Ingestion Commands:**
```bash
python -m src.main papers       # Ingest research papers
python -m src.main startups     # Ingest AI startups
python -m src.main products     # Ingest AI products
python -m src.main jobs         # Ingest AI jobs (past 24h)
python -m src.main news         # Ingest AI news (past 24h)
```

**Audit Command:**
```bash
python -m src.main audit        # Validates database integrity and displays extraction statistics
```

**Export Commands:**
```bash
python -m src.main export --format jsonl  # Exports database records to data/*.jsonl
python convert_to_csv.py                  # Flattens and converts JSONL exports to CSV
python generate_mapping_log.py            # Generates the entity resolution mapping log
```

## Data Outputs

All exported files are written to the `data/` directory.

- `research_papers.jsonl` / `.csv` (1,300 records)
- `startups.jsonl` / `.csv` (1,225 records)
- `products.jsonl` / `.csv` (1,411 records)
- `jobs.jsonl` / `.csv` (171 records)
- `news.jsonl` / `.csv` (13 records)
- `entity_mapping_log.csv` (2,807 mapping records)

*Note: The numbers reflect successfully verified and exported records present in the final datasets.*

## Validation & Testing

The system's integrity is continually verified by an automated test suite covering parsing, serialization constraints, engine retry behavior, network handling, schema compliance, and temporal freshness logic.

- **Pytest**: 41/41 tests passing.
- **Execution**: Run the full suite using `python -m pytest tests/ -v`.

Additionally, the `python -m src.main audit` command performs runtime validation over the persisted data, asserting uniqueness constraints and flagging incomplete entity formations.

## Engineering Decisions

- **Asynchronous I/O**: Network-bound ingestion is heavily parallelized utilizing `asyncio` and `aiohttp`, allowing the system to scale gracefully without thread-blocking overhead.
- **Deterministic Normalization**: Prioritized over heuristic matching to guarantee predictable deduplication and prevent false positives during entity relationship mapping.
- **Strict Validation**: Pydantic schemas enforce type safety and constraints (e.g. valid URLs, positive integers) at the application boundary, protecting the database from polluted state.
- **Separation of Concerns**: Crawling (I/O), parsing (CPU), validation, and persistence are deliberately uncoupled to simplify testing and allow independent scaling of components.
- **Controlled Concurrency**: Implements explicit rate limiting and verification to operate respectfully against upstream sources, mitigating IP bans.

## Limitations

- **Dynamic JavaScript Content**: The current crawler relies primarily on static HTML and accessible API/feed endpoints. Highly dynamic sites that require client-side JavaScript rendering cannot be fully extracted without a headless browser integration.
- **Deterministic Resolution Restrictions**: Entities with severe typographical errors or radical rebranding are occasionally not recognized as identical due to the deliberate absence of fuzzy logic.
- **Strict Exclusions**: To maintain zero hallucination tolerance, records lacking mandatory fields (e.g., a product lacking pricing data) are fully discarded, mildly reducing potential throughput in favor of absolute quality.

## Roadmap

Future iterations of the AtlasIngest architecture may target:
- **Dynamic Content Extraction**: Integration with Playwright for reliable ingestion of JS-heavy SPAs.
- **LLM-Assisted Extraction**: Opt-in semantic parsing for entirely unstructured documents (e.g., press releases) while retaining strict validation boundaries.
- **Additional Source Connectors**: Expanding domain coverage to financial filings and GitHub activity.
- **Incremental Scheduling**: Transitioning from batch CLI triggers to cron-driven delta updates.
- **Enhanced Observability**: Emitting rich OpenTelemetry traces for deeper ingestion monitoring.

## Documentation

- System Architecture: [architecture.pdf](architecture.pdf)
- Main Entrypoint: [src/main.py](src/main.py)
