# Website-to-Database ELT Pipeline

A modular Python project that extracts data from public websites, loads the raw data into a SQLite database, and transforms it into clean, structured, analysis-ready data using SQL.

## 1. Project Overview

The Website-to-Database ELT Pipeline automates the process of collecting data from a website and preparing it for further use.

Users provide a website URL, and the application extracts supported webpage content, stores the raw records in a database, and transforms the stored data into a clean and structured format.

The project follows the **ELT (Extract, Load, Transform)** approach, where data is loaded before transformations are applied.

The application runs locally and displays execution results through the terminal. It does not require a dashboard, login system, or frontend application.

## 2. Problem Statement

Collecting information from websites manually can be time-consuming, repetitive, and difficult to organize.

This project aims to automate website data collection and preparation through a reusable pipeline that can extract webpage content, preserve the original data, and transform it into structured database records.

## 3. Project Objectives

- Accept a website URL as input.
- Extract supported content from publicly accessible webpages.
- Store extracted data in SQLite before transformation.
- Clean and validate data using SQL.
- Identify and handle duplicate records.
- Maintain pipeline execution logs and error information.
- Organize the application using a modular architecture.
- Test the complete ELT workflow locally.
- Prepare the application for deployment after development is complete.

## 4. How the Pipeline Works

The pipeline follows three main stages.

### Extract

- Accept a website URL.
- Fetch the webpage using Python Requests.
- Parse accessible HTML using Beautiful Soup.
- Extract available fields such as page titles, headings, links, and supported tabular content.
- Validate the response and handle extraction errors.

### Load

- Store extracted records in a SQLite database.
- Preserve the original extracted content in a raw-data table.
- Record the source URL and extraction timestamp.
- Track pipeline runs and their status.

### Transform

- Remove unwanted whitespace and normalize text.
- Handle missing or invalid values.
- Identify duplicate records.
- Convert extracted information into structured database tables.
- Save the cleaned results separately from the raw data.

**Pipeline flow:**

`Website URL → Extract → Load Raw Data → Transform with SQL → Structured Data`

## 5. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Requests | Fetch webpage content |
| Beautiful Soup | Parse HTML and extract data |
| SQLite | Store raw and transformed data |
| SQL | Clean, validate, and structure data |
| pytest | Automated testing |
| Git | Version control |

Playwright or another browser automation tool may be considered later if support for JavaScript-rendered websites becomes necessary.

## 6. System Architecture

The application will use a modular architecture with separate components for configuration, extraction, database operations, transformations, and pipeline orchestration.

The main workflow is:

1. The user supplies a URL.
2. The extraction module retrieves and parses supported webpage content.
3. The loading module saves raw records to SQLite.
4. The transformation module processes the loaded records using SQL.
5. The pipeline runner coordinates execution and reports the outcome.
6. The logging module records successful runs and errors.

Each module will have a clear responsibility so that it can be tested and maintained independently.

## 7. Planned Folder Structure

```text
website-elt-pipeline/
├── config/
│   └── settings.py
├── data/
│   └── .gitkeep
├── database/
│   ├── connection.py
│   └── schema.sql
├── extractor/
│   ├── __init__.py
│   └── scraper.py
├── loader/
│   ├── __init__.py
│   └── raw_loader.py
├── transformations/
│   ├── __init__.py
│   └── transform.sql
├── pipeline/
│   ├── __init__.py
│   └── runner.py
├── logs/
│   └── .gitkeep
├── tests/
│   └── test_pipeline.py
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

The structure may be refined during Phase 1, but the separation of responsibilities must be maintained.

## 8. Database Design

SQLite will initially contain separate tables for raw data, transformed data, and pipeline execution history.

### Raw Data Table

Stores extracted records before transformation.

Example fields:

- `id`
- `source_url`
- `page_title`
- `content`
- `extracted_at`

### Transformed Data Table

Stores cleaned and structured records.

Example fields:

- `id`
- `source_url`
- `page_title`
- `content`
- `transformed_at`

### Pipeline Runs Table

Tracks pipeline execution.

Example fields:

- `run_id`
- `source_url`
- `started_at`
- `completed_at`
- `status`
- `records_extracted`
- `error_message`

The final schema will depend on the supported extraction format. Different websites may expose different fields, so the application must handle variable content without assuming that every webpage has the same structure.

## 9. Development Roadmap

The project will be completed in six phases. Each phase must be tested before proceeding to the next.

### Phase 1 — Project Setup

- Initialize the project and virtual environment.
- Install dependencies.
- Create the modular folder structure.
- Configure application settings.
- Establish the SQLite connection.
- Define the initial database schema.
- Verify that the application starts successfully.

**Expected outcome:** A working project foundation with database connectivity.

### Phase 2 — Website Extraction

- Accept a URL through the command line.
- Validate the URL.
- Fetch accessible webpage content.
- Parse HTML using Beautiful Soup.
- Extract supported content fields.
- Handle timeouts, HTTP errors, and invalid responses.
- Test extraction against suitable public webpages.

**Expected outcome:** A reusable extraction module that returns structured records.

### Phase 3 — Database Loading

- Create the raw-data storage workflow.
- Load extracted records into SQLite.
- Store source URLs and extraction timestamps.
- Handle database errors and empty extraction results.
- Verify that records persist after the application exits.

**Expected outcome:** Successfully extracted data stored in the raw-data table.

### Phase 4 — SQL Transformations

- Read records from the raw-data table.
- Clean whitespace and normalize text.
- Handle missing values.
- Identify duplicate records.
- Insert cleaned records into the transformed-data table.
- Validate transformation results.

**Expected outcome:** Cleaned, structured data stored separately from the original data.

### Phase 5 — Pipeline Integration

- Connect extraction, loading, and transformation modules.
- Implement a single pipeline execution command.
- Track pipeline runs and record counts.
- Add consistent logging and error handling.
- Ensure failures are reported clearly.
- Test the complete end-to-end workflow.

**Expected outcome:** One command executes the complete ELT pipeline.

### Phase 6 — Testing and Deployment Preparation

- Run unit and integration tests.
- Test invalid URLs, empty pages, and failed requests.
- Validate raw and transformed database records.
- Improve configuration and error messages.
- Finalize documentation and setup instructions.
- Prepare the application for deployment where appropriate.

**Expected outcome:** A tested, documented, reproducible ELT application.

## 10. Installation

### Prerequisites

- Python 3.11 or later
- pip
- Git (optional)

### Setup

Clone the repository or open the project directory, then create a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project dependencies after `requirements.txt` has been created:

```powershell
pip install -r requirements.txt
```

Run the application using the entry point implemented during development:

```powershell
python main.py
```

The exact command-line arguments will be documented when the pipeline runner is implemented.

## 11. Example Usage

A completed version of the application will support a workflow similar to:

```text
Enter website URL:
https://example.com

[1/3] Extracting webpage data...
[2/3] Loading raw data into SQLite...
[3/3] Transforming data using SQL...

Pipeline completed successfully.

Records extracted: 15
Records loaded: 15
Records transformed: 15
Status: SUCCESS
```

These numbers are illustrative only. Actual results will depend on the website and the records available.

## 12. Error Handling and Reliability

The application should handle:

- Invalid or malformed URLs.
- Connection failures and request timeouts.
- HTTP error responses.
- Empty or unsupported webpages.
- Missing webpage fields.
- Duplicate records.
- SQLite connection and insertion errors.
- SQL transformation failures.

Failed runs should be logged with useful diagnostic information. Sensitive information, if any, must not be written to logs.

## 13. Scope and Limitations

### Included

- URL-based webpage extraction.
- Support for selected public HTML content.
- SQLite raw-data storage.
- SQL-based transformations.
- Pipeline execution history.
- Terminal output and logging.
- Automated tests.

### Not included in the initial version

- Web dashboard or graphical frontend.
- User registration or authentication.
- Cloud data warehouses.
- Distributed processing tools such as Spark.
- Automatic crawling of entire websites.
- Bypassing authentication, paywalls, CAPTCHAs, or anti-bot restrictions.
- Guaranteed support for every website or dynamically rendered page.

Website access rules, terms of service, and applicable laws must be respected. Where appropriate, official APIs should be preferred over scraping.

## 14. Testing Strategy

Testing will be performed throughout development.

- **Unit tests:** Validate individual extraction, loading, and transformation functions.
- **Database tests:** Verify schema creation and data persistence.
- **Transformation tests:** Confirm cleaning and duplicate handling.
- **Integration tests:** Verify that all pipeline stages work together.
- **Error tests:** Check invalid URLs, failed requests, and database errors.

Tests should use controlled HTML fixtures or suitable test pages so they do not depend unnecessarily on external website availability.

## 15. Future Enhancements

After the six-phase project is complete, possible extensions include:

- Support for multiple website templates.
- Scheduled extraction jobs.
- Incremental data loading.
- Support for JavaScript-rendered pages.
- Additional database backends.
- Export to CSV or JSON.
- Data quality reports.

These are optional future improvements and will not be implemented prematurely.

## 16. Project Success Criteria

The project will be considered complete when:

- A user can provide a supported public website URL.
- The application extracts available content.
- Raw records are stored in SQLite.
- SQL transformations produce clean, structured records.
- Pipeline runs and errors are recorded.
- The complete workflow executes reliably.
- Automated tests pass.
- Setup and execution instructions are documented.

## Conclusion

The Website-to-Database ELT Pipeline demonstrates the practical application of web scraping, database loading, SQL transformations, modular Python development, and automated testing.

Its focus is on building a real, working data engineering pipeline that is simple to run, easy to understand, and extensible without unnecessary complexity.
