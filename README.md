# Website-to-Database ELT Pipeline

A modular, production-grade Python ELT (Extract, Load, Transform) data pipeline that extracts structured content from public webpages, loads raw records into a local SQLite database, and cleans, normalizes, and structures the data using SQL transformations.

---

## 1. Project Overview & Objectives

The **Website-to-Database ELT Pipeline** automates the acquisition, preservation, and structured preparation of web-based textual data.

Traditional web scrapers frequently combine extraction and cleaning into a single tightly coupled step (ETL). This pipeline instead adheres to the **ELT (Extract, Load, Transform)** paradigm:
1. **Extract**: Fetch and parse accessible webpage content from a public URL.
2. **Load**: Persist the raw, unaltered structured payload into SQLite immediately with extraction timestamps and content fingerprints.
3. **Transform**: Clean, normalize, validate, and deduplicate records directly in SQLite using transactional SQL operations, saving the results in a separate analysis-ready table.

### Core Objectives
- **Command-Line Interface**: Run the entire ELT workflow or individual stages via clean CLI commands.
- **Data Integrity**: Guarantee that raw data remains immutable and available for auditing or future transformations.
- **Idempotency & Deduplication**: Compute deterministic SHA-256 fingerprints to prevent duplicate storage across repeated runs while preserving distinct versions when page content updates.
- **Defensive Security**: Enforce strict URL validation with Server-Side Request Forgery (SSRF) defense, loopback/private IP blocking, redirect hop revalidation, and response size limits.
- **Auditable History & Safe Logging**: Record every pipeline execution in a dedicated `pipeline_runs` table with UTC timestamps, status metrics, and sanitized log output without sensitive parameters.
- **Tested & Deployable**: Complete automated test suite using isolated SQLite databases and mock fixtures, with zero external network dependencies.

---

## 2. ELT Architecture & Workflow

The pipeline coordinates three distinct processing stages:

```text
                                  +-----------------------+
                                  |   Target Public URL   |
                                  +-----------+-----------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------+
| [1/3] EXTRACTION STAGE (extractor/scraper.py)                                           |
| - URL syntax validation & SSRF defense (blocks private IPs, cloud metadata, loopback)   |
| - Streaming HTTP GET with response-size limit (5 MB) & redirect revalidation            |
| - HTML parsing via Beautiful Soup (title, headings, resolved links, body text)          |
+---------------------------------------------+-------------------------------------------+
                                              | Raw Structured Payload
                                              v
+-----------------------------------------------------------------------------------------+
| [2/3] LOADING STAGE (loader/raw_loader.py)                                              |
| - Required field validation (source_url, extracted_at)                                  |
| - Deterministic JSON serialization of headings and links                                |
| - SHA-256 content fingerprint calculation                                               |
| - Idempotent insertion into SQLite raw_data table                                       |
+---------------------------------------------+-------------------------------------------+
                                              | Raw Records Preserved
                                              v
+-----------------------------------------------------------------------------------------+
| [3/3] TRANSFORMATION STAGE (transformations/transformer.py)                             |
| - Atomic SQLite transaction with automatic rollback                                     |
| - Text whitespace normalization & empty string to NULL conversion                       |
| - Headings and links JSON validation & cleaning                                         |
| - Content-hash deduplication against transformed_data table                             |
| - Insertion into transformed_data table with foreign key linkage (raw_id)               |
+---------------------------------------------+-------------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------------+
| EXECUTION TRACKING (pipeline/runner.py & logs/pipeline.log)                             |
| - Real-time terminal execution summary                                                  |
| - Persistent run history in pipeline_runs table (RUNNING, SUCCESS, FAILED)              |
| - Structured console and rotating file logging with URL parameter sanitization          |
+-----------------------------------------------------------------------------------------+
```

---

## 3. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | **Python (3.11+)** | Standard language for data engineering and scripting |
| HTTP Client | **Requests (>=2.31.0)** | Robust streaming HTTP requests with redirect handling |
| HTML Parser | **Beautiful Soup 4 (>=4.12.0)** | Resilient DOM parsing and element extraction |
| Database | **SQLite 3** | Self-contained, zero-configuration local relational database |
| Language/Engine | **SQL** | Declarative data cleaning, normalization, and deduplication |
| Test Framework | **pytest (>=8.0.0)** | Fixture-based automated unit and regression testing |
| Version Control | **Git** | Distributed version control with strict data/log exclusion |

---

## 4. Actual Project Folder Structure

```text
Website-to-Database-ELT-Pipeline/
├── config/
│   ├── __init__.py
│   └── settings.py          # Centralized paths, timeouts, size limits, logging setup
├── data/
│   ├── .gitkeep             # Preserves directory in git
│   └── pipeline.db          # Local SQLite database (git-ignored)
├── database/
│   ├── __init__.py
│   ├── connection.py        # Connection manager (Row factory) and schema migration
│   └── schema.sql           # DDL schema for raw_data, transformed_data, pipeline_runs
├── extractor/
│   ├── __init__.py
│   └── scraper.py           # Web scraper, SSRF prevention, HTML parsing, URL sanitizer
├── loader/
│   ├── __init__.py
│   └── raw_loader.py        # Raw SQLite loader with SHA-256 duplicate detection
├── logs/
│   ├── .gitkeep             # Preserves directory in git
│   └── pipeline.log         # Application execution log file (git-ignored)
├── pipeline/
│   ├── __init__.py
│   └── runner.py            # End-to-end ELT coordinator & pipeline_runs history tracker
├── tests/
│   ├── __init__.py
│   ├── test_database.py     # Database schema, connectivity, and idempotency tests
│   ├── test_loader.py       # Raw loading, JSON serialization, and rollback tests
│   ├── test_pipeline.py     # End-to-end pipeline, stage halt, and CLI integration tests
│   ├── test_scraper.py      # URL safety, SSRF, parsing, and extraction tests
│   └── test_transformer.py  # SQL cleaning, normalization, and deduplication tests
├── transformations/
│   ├── __init__.py
│   └── transformer.py       # SQL transformation engine, normalization, and deduplication
├── .gitignore               # Strict exclusion of virtual envs, caches, db, and logs
├── main.py                  # CLI application entry point and argument dispatcher
├── README.md                # Comprehensive documentation
└── requirements.txt         # Minimal production and testing dependencies
```

---

## 5. Prerequisites & Environment Setup

### Prerequisites
- **Python**: Version 3.11 or later
- **pip**: Python package installer
- **Git** (optional for cloning)

### Installation & Virtual Environment Setup

#### Windows (PowerShell)
```powershell
# 1. Clone repository or navigate to workspace
cd Website-to-Database-ELT-Pipeline

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
```

#### macOS / Linux (bash/zsh)
```bash
# 1. Clone repository or navigate to workspace
cd Website-to-Database-ELT-Pipeline

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## 6. Database Location & Schema

The application automatically stores its relational data in a local SQLite file at:
`data/pipeline.db`

The schema is declared in `database/schema.sql` and initialized automatically on startup.

### Schema Definition

```sql
-- 1. Raw Data Table: Stores raw extracted payloads before transformation
CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    page_title TEXT,
    headings TEXT,            -- Serialized JSON array of strings
    links TEXT,               -- Serialized JSON array of {"text": ..., "url": ...}
    content TEXT,             -- Clean readable body text
    content_hash TEXT,        -- Deterministic SHA-256 fingerprint
    extracted_at TEXT NOT NULL -- ISO 8601 UTC timestamp
);

-- 2. Transformed Data Table: Stores cleaned, normalized, structured records
CREATE TABLE IF NOT EXISTS transformed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER,           -- Foreign reference to raw_data.id
    source_url TEXT NOT NULL,
    page_title TEXT,          -- Normalized title or NULL if absent
    headings TEXT,            -- Validated JSON array of cleaned headings
    links TEXT,               -- Validated JSON array of valid URLs
    content TEXT,             -- Normalized readable content
    content_hash TEXT,        -- Transformed content SHA-256 fingerprint
    transformed_at TEXT NOT NULL -- ISO 8601 UTC timestamp
);

-- 3. Pipeline Runs Table: Execution metadata and history tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,     -- 'RUNNING', 'SUCCESS', or 'FAILED'
    records_extracted INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

-- Performance & Deduplication Indexes
CREATE INDEX IF NOT EXISTS idx_raw_data_source_url ON raw_data (source_url);
CREATE INDEX IF NOT EXISTS idx_raw_data_content_hash ON raw_data (source_url, content_hash);
CREATE INDEX IF NOT EXISTS idx_transformed_data_source_url ON transformed_data (source_url);
CREATE INDEX IF NOT EXISTS idx_transformed_data_hash ON transformed_data (source_url, content_hash);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source_url ON pipeline_runs (source_url);
```

---

## 7. How to Run the Application

The CLI entry point is `main.py`.

### Supported Command-Line Options

| Command | Option | Description |
|---|---|---|
| `python main.py` | *(none)* | Initializes runtime directories and ensures SQLite database schema is created (Phase 1). |
| `python main.py --url <URL>` | `--url` | Executes the complete end-to-end ELT pipeline for the URL (Phase 5). |
| `python main.py --url <URL> --extract-only` | `--extract-only` | Runs extraction only and prints structured data without database modification (Phase 2). |
| `python main.py --verify-loader` | `--verify-loader` | Verifies database loading and duplicate handling with sample data (Phase 3). |
| `python main.py --transform` | `--transform` | Executes SQL transformations on all existing unprocessed raw records (Phase 4). |
| `python main.py --help` | `-h`, `--help` | Displays available arguments and usage instructions. |

### CLI Usage Examples

#### 1. Execute Complete ELT Pipeline
```bash
python main.py --url https://example.com
```

**Terminal Output Example:**
```text
=================================================================
 Website-to-Database ELT Pipeline
 Phase 5: End-to-End Pipeline Execution
=================================================================
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Initiating full ELT pipeline for: https://example.com
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Database schema initialized successfully at: ...\data\pipeline.db
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Pipeline run #17 started for: https://example.com
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Pipeline run #17: [1/3] Extracting webpage data...
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Fetching URL: https://example.com
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Pipeline run #17: [2/3] Loading raw data into SQLite...
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Loading raw data for: https://example.com
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Pipeline run #17: [3/3] Transforming data using SQL...
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Starting transformation run on database: ...\data\pipeline.db
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Transformation completed: 1 inserted, 0 duplicates skipped, 0 invalid records skipped.
[2026-10-17 22:07:17] [INFO] [elt_pipeline]: Pipeline run #17 completed successfully for: https://example.com
Run ID:            17
Source URL:        https://example.com
Overall Status:    SUCCESS
-----------------------------------------------------------------
 [1/3] EXTRACTION:
   Page Title:       Example Domain
   Headings Found:   1
   Links Found:      1
   Content Preview:  This domain is for use in documentation examples without needing permission...
-----------------------------------------------------------------
 [2/3] LOADING (Raw Data):
   Load Status:      INSERTED
   Raw Record ID:    1
   Newly Inserted:   True
-----------------------------------------------------------------
 [3/3] TRANSFORMATION (SQL):
   Cleaned Records:  1
   Transformed Rows: 1
   Duplicates Stored:0
=================================================================
Pipeline execution completed successfully.
=================================================================
```

#### 2. Extract Webpage Content Only (No Database Storage)
```bash
python main.py --url https://example.com --extract-only
```

#### 3. Transform Existing Raw Records
```bash
python main.py --transform
```

#### 4. Verify Database Loader
```bash
python main.py --verify-loader
```

---

## 8. Detailed Pipeline Mechanics

### Extraction Engine (`extractor/scraper.py`)
- **Strict URL Validation**: Enforces valid `http` or `https` schemes, requires hostnames, and blocks embedded userinfo (`user:pass@host`).
- **SSRF Defense**: Resolves domain names via DNS and verifies IP addresses against `ipaddress.is_loopback`, `ipaddress.is_private`, `is_link_local`, `is_reserved`, and non-global blocks (e.g., AWS metadata `169.254.169.254`, `127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`).
- **Streaming Size & Timeout Safeguards**:
  - `REQUEST_TIMEOUT = 10` seconds prevents hanging connections.
  - `MAX_RESPONSE_SIZE = 5 MB` streaming chunk-size check prevents denial-of-service from memory exhaustion.
  - Redirect revalidation: Manually traces redirects up to `MAX_REDIRECTS = 5`, re-verifying every destination against SSRF rules before making the next hop.
- **Content Parsing**: Beautiful Soup decomposes `<script>`, `<style>`, `<noscript>`, `<svg>`, and `<iframe>` tags, extracting clean titles, structured headings (H1–H6), absolute-resolved hyperlinks, and clean body text.

### Raw Loading Engine (`loader/raw_loader.py`)
- **Immutability**: Inserts the extracted record into `raw_data` preserving the exact extracted structure.
- **Deterministic Fingerprinting**: Generates SHA-256 fingerprint:
  `SHA-256(source_url | page_title | headings_json | links_json | content)`
- **Duplicate Prevention vs. Versioning**:
  - If a record with the same `source_url` and `content_hash` exists, insertion is safely skipped (`status: DUPLICATE`).
  - If page content has changed on a subsequent crawl, the new version is recorded with a new primary key and timestamp.

### SQL Transformation Engine (`transformations/transformer.py`)
- **ELT Preservation**: Reads unprocessed rows from `raw_data` without modifying or deleting them.
- **Data Normalization**:
  - Collapses duplicate whitespace, tabs, and newlines.
  - Converts empty or whitespace-only strings to `NULL`.
  - Recovers content from headings if body text is sparse.
  - Safely parses and normalizes JSON headings and link URLs.
- **Atomic Transactions**: All transformation steps run inside a SQLite transaction context manager. Any error triggers an immediate rollback, leaving the database consistent.
- **Idempotency**: Repeated runs on unchanged data will not generate duplicate rows in `transformed_data`.

---

## 9. Logging & Execution History

### Logging
- Runtime logs are written to standard output and persisted to:
  `logs/pipeline.log`
- Format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [LOGGER]: Message`
- **Security & Privacy**: URLs logged across scraper, loader, transformer, and CLI entry points are passed through `sanitize_url_for_logging`, stripping embedded credentials and redacting query strings (e.g., `https://example.com/api?...`).

### Execution History (`pipeline_runs`)
Every pipeline execution writes a tracking record:
- `run_id`: Unique run identifier.
- `source_url`: The targeted URL.
- `started_at` & `completed_at`: UTC timestamps.
- `status`: `'RUNNING'` upon startup, updated to `'SUCCESS'` or `'FAILED'`.
- `records_extracted`: Record counter.
- `error_message`: Captured diagnostic message if any stage fails.

---

## 10. Automated Testing

All tests run in total isolation using temporary SQLite databases (`tmp_path` fixture) and mocked HTTP/DNS calls. No test depends on live external websites.

### Run Test Suite
```bash
# Run pytest with verbose test progress
pytest -v

# Or using the virtual environment python module
python -m pytest -v
```

### Test Coverage Areas
1. **Database Tests (`tests/test_database.py`)**:
   - SQLite `sqlite3.Row` row factory configuration.
   - Idempotent schema initialization (`init_db`).
   - Expected tables (`raw_data`, `transformed_data`, `pipeline_runs`) and column definitions.
   - Clean initial database state without mock data pollution.
2. **Scraper Tests (`tests/test_scraper.py`)**:
   - URL validation (HTTP/HTTPS, empty, malformed, unsupported schemes).
   - SSRF defenses (localhost, private LAN IPs, cloud metadata IP, DNS rebinding).
   - HTML parsing, title fallback, heading collection, link resolution, whitespace cleanup.
   - HTTP timeouts, 4xx/5xx responses, streaming size limit enforcement, redirect revalidation.
   - Phase 2 CLI `--extract-only` verification.
3. **Loader Tests (`tests/test_loader.py`)**:
   - Valid record insertion into `raw_data`.
   - Complex field preservation (headings and links JSON serialization).
   - Missing required field rejection (`source_url`, `extracted_at`).
   - Deterministic SHA-256 duplicate detection.
   - Content change versioning.
   - Transaction rollback on simulated database failures.
   - URL sanitization for logs.
4. **Transformer Tests (`tests/test_transformer.py`)**:
   - Text cleaning, normalization, and NULL conversion for whitespace.
   - Fallback to headings when content is missing.
   - Tolerance to malformed optional JSON.
   - Deduplication in `transformed_data`.
   - Idempotent repeated execution.
   - Transaction rollback on operational error.
5. **Pipeline Integration Tests (`tests/test_pipeline.py`)**:
   - End-to-end Extract -> Load -> Transform flow.
   - History recording in `pipeline_runs` (`SUCCESS` and `FAILED`).
   - Stage failure halts (extraction failure stops loading; loading failure stops transformation).
   - Preservation of raw records when transformation fails.
   - Phase 3, 4, and 5 CLI options (`--url`, `--verify-loader`, `--transform`, `--extract-only`).

---

## 11. Security & Data Integrity

The codebase incorporates defensive security best practices:
- **SSRF Prevention**: All target URLs and redirect locations are resolved and validated against private, link-local, multicast, loopback, and reserved IP ranges.
- **Credential Protection**: URLs with embedded usernames or passwords (`user:pass@host`) are rejected outright by the validation engine and redacted from all log statements.
- **Resource Protection**:
  - `REQUEST_TIMEOUT = 10` seconds prevents worker stalling.
  - `MAX_RESPONSE_SIZE = 5 MB` streaming chunk check prevents memory exhaustion attacks.
  - `MAX_REDIRECTS = 5` stops infinite redirect loops.
- **SQL Injection Prevention**: 100% of queries with dynamic user or scraped values use parameterized SQL placeholders (`?`).
- **Connection & Resource Cleanup**: Every SQLite connection and HTTP streaming response is wrapped in `try...finally` or context managers, ensuring connections are closed under all execution paths.
- **Transaction Atomicity**: Database insertions and transformations execute within transactions that automatically roll back upon failure.

---

## 12. Deployment Preparation

### Clean Environment Checklist
1. **Python Installation**: Ensure Python 3.11+ is installed.
2. **Virtual Environment**: Create and activate a clean `.venv`.
3. **Dependencies**: Run `pip install -r requirements.txt`.
4. **Execution**: Run `python main.py` to initialize tables, or `python main.py --url <URL>` to execute a pipeline run.

### Storage Persistence Considerations
- **Local File Storage**: SQLite stores all data in a local file at `data/pipeline.db`.
- **Ephemeral Containers**: If deploying on container platforms (Docker, Kubernetes, AWS ECS, Google Cloud Run), local container storage is ephemeral. To persist database records and logs across container restarts or redeployments:
  - Mount a persistent volume to the `data/` directory (e.g., `-v /persistent/path/data:/app/data`).
  - Mount a persistent volume to the `logs/` directory for log retention.
- **Portable Relative Paths**: The configuration in `config/settings.py` resolves all paths relative to `BASE_DIR = Path(__file__).resolve().parent.parent`, eliminating hardcoded machine-specific paths and allowing the application to run from any directory.

---

## 13. Scope & Known Limitations

### Current Capabilities
- Automated extraction of public, static HTML pages.
- Immediate preservation of raw extracted data.
- Deduplication and text cleaning via SQL.
- Auditable execution history in SQLite.
- Safe logging without credentials.

### Known Limitations
- **Single-URL CLI Execution**: The CLI processes one URL per invocation; batch execution requires a shell loop or external runner.
- **Static HTML Only**: Webpages requiring JavaScript client-side rendering (Single Page Applications built with React/Vue/Angular that fetch data via client-side AJAX) will only yield initial static HTML. Browser automation (e.g., Playwright) is outside the initial pipeline scope.
- **Local Concurrency**: SQLite supports high read concurrency but serializes writes. Highly concurrent multi-threaded or distributed writers should migrate the database connection to PostgreSQL if needed.
- **No Inbuilt Task Scheduler**: The pipeline runs on-demand. Recurring scheduled runs should be triggered via OS-level schedulers (cron on Linux/macOS, Windows Task Scheduler) or orchestrators.

---

## 14. Responsible Website Scraping Practices

When scraping public websites with this pipeline:
1. **Review `robots.txt`**: Check the target domain's `/robots.txt` file and adhere to crawling directives and disallowed paths.
2. **Respect Terms of Service**: Verify that automated data extraction is permitted by the website's terms of use.
3. **Avoid Aggressive Request Rates**: Limit the frequency of pipeline runs to avoid overloading website servers.
4. **Use Explicit User-Agents**: The pipeline provides an identifiable user-agent (`WebsiteELTPipelineBot/1.0`) configured in `config/settings.py`.
5. **Prefer Public APIs**: When a website provides an official REST or GraphQL API, utilize the API in preference to HTML scraping.
6. **Protect Personal Data**: Adhere to applicable data protection regulations (e.g., GDPR, CCPA) when extracting information containing personal identifiers.

---

## 15. Development Roadmap & Phase Status

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Project Setup, Modular Architecture & SQLite Schema Initialization | **[Completed]** |
| **Phase 2** | Website Extraction Engine, SSRF Defense, HTML Parsing & Scraper CLI | **[Completed]** |
| **Phase 3** | Raw Data Database Loading, SHA-256 Duplicate Handling & Versioning | **[Completed]** |
| **Phase 4** | SQL Transformation Engine, Normalization, Text Cleaning & Deduplication | **[Completed]** |
| **Phase 5** | End-to-End Pipeline Integration, History Tracking & Unified CLI | **[Completed]** |
| **Phase 6** | Final Testing, Security & Integrity Review, Documentation & Deployment Prep | **[Completed]** |

---

## 16. Summary

The Website-to-Database ELT Pipeline provides a complete, robust, and verified implementation of the Extract-Load-Transform methodology for web data engineering. It demonstrates reliable web extraction, immediate raw data preservation, SQL-based normalization, deterministic deduplication, and auditable history tracking in a lightweight, maintainable architecture.
