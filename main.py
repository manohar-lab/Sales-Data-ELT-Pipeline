"""Website-to-Database ELT Pipeline - Application Entry Point.

Supports Phase 1 database initialization (when run without arguments)
and Phase 2 website extraction (when run with --url <URL>).
"""

import argparse
import sys
from typing import Optional, Sequence

from config import settings
from database.connection import init_db
from extractor.scraper import ExtractionError, extract_page_data


def run_phase_1_setup() -> int:
    """Run the Phase 1 startup sequence (database and runtime directory initialization)."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 1: Project Setup & Database Initialization")
    print("=" * 65)

    logger = settings.setup_logging()

    try:
        # Step 1: Ensure runtime directories exist
        settings.init_directories()
        logger.info("Runtime directories initialized.")

        # Step 2: Initialize SQLite database and tables
        init_db()
        logger.info("SQLite database and tables initialized successfully.")

        # Step 3 & 4: Display status and path
        print(f"Database File:   {settings.DATABASE_PATH.resolve()}")
        print("Database Status: Successfully initialized (tables created)")
        print(f"Logs Directory:  {settings.LOGS_DIR.resolve()}")
        print("=" * 65)
        print("Phase 1 initialization complete. System is ready for Phase 2.")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"Error during database initialization: {exc}", file=sys.stderr)
        logger.error(f"Startup failed: {exc}", exc_info=True)
        return 1


def run_phase_2_extraction(url: str) -> int:
    """Run the Phase 2 website extraction sequence for a target URL."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 2: Website Extraction Engine")
    print("=" * 65)

    logger = settings.setup_logging()
    logger.info(f"Starting extraction for URL: {url}")

    try:
        data = extract_page_data(url)
        logger.info(f"Successfully extracted data from: {url}")

        # Display extracted summary
        print(f"Source URL:       {data['source_url']}")
        print(f"Page Title:       {data['page_title'] or '(No title found)'}")
        print(f"Headings Found:   {len(data['headings'])}")
        print(f"Links Found:      {len(data['links'])}")

        content_preview = data["content"][:200] + ("..." if len(data["content"]) > 200 else "")
        print(f"Content Preview:  {content_preview or '(No readable text)'}")
        print(f"Extracted At:     {data['extracted_at']}")
        print("=" * 65)
        print("Phase 2 extraction completed successfully.")
        print("=" * 65)
        return 0

    except ExtractionError as exc:
        print(f"Extraction Error: {exc}", file=sys.stderr)
        logger.error(f"Extraction failed for {url}: {exc}")
        return 1
    except Exception as exc:
        print(f"Unexpected Error: {exc}", file=sys.stderr)
        logger.error(f"Unexpected failure during extraction for {url}: {exc}", exc_info=True)
        return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse command line arguments and execute the requested pipeline task."""
    parser = argparse.ArgumentParser(
        description="Website-to-Database ELT Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Target website URL to extract data from (Phase 2).",
    )

    args = parser.parse_args(argv)

    if args.url:
        return run_phase_2_extraction(args.url)
    else:
        return run_phase_1_setup()


if __name__ == "__main__":
    sys.exit(main())
