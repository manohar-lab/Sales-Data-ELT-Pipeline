"""Website-to-Database ELT Pipeline - Application Entry Point.

Supports:
- Phase 1: Database initialization (run without arguments)
- Phase 2: Website extraction only (run with --url <URL> --extract-only)
- Phase 3: Database loading verification (run with --verify-loader)
- Phase 4: SQL transformations only (run with --transform)
- Phase 5: Complete end-to-end ELT pipeline (run with --url <URL>)
"""

import argparse
import sys
from typing import Optional, Sequence

from config import settings
from database.connection import init_db
from extractor.scraper import ExtractionError, extract_page_data
from loader.raw_loader import get_raw_record, load_raw_data
from pipeline.runner import run_pipeline
from transformations.transformer import TransformationError, transform_raw_data


def run_phase_1_setup() -> int:
    """Run the Phase 1 startup sequence (database and runtime directory initialization)."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 1: Project Setup & Database Initialization")
    print("=" * 65)

    logger = settings.setup_logging()

    try:
        settings.init_directories()
        logger.info("Runtime directories initialized.")

        init_db()
        logger.info("SQLite database and tables initialized successfully.")

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
    """Run Phase 2 extraction only without database loading."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 2: Website Extraction Engine")
    print("=" * 65)

    logger = settings.setup_logging()
    logger.info(f"Starting extraction for URL: {url}")

    try:
        data = extract_page_data(url)
        logger.info(f"Successfully extracted data from: {url}")

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


def run_phase_3_verify_loader() -> int:
    """Verify Phase 3 database loading and duplicate handling with sample data."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 3: Database Loading Verification")
    print("=" * 65)

    logger = settings.setup_logging()

    try:
        settings.init_directories()
        init_db()

        test_data = {
            "source_url": "https://example.com/loader-test",
            "page_title": "Loader Test Page",
            "headings": ["Test Heading 1", "Test Heading 2"],
            "links": [{"text": "Example Link", "url": "https://example.com/target"}],
            "content": "Sample content used to verify the Phase 3 loading engine.",
            "extracted_at": "2026-10-16T12:00:00+00:00",
        }

        logger.info("Executing test insert...")
        res1 = load_raw_data(test_data)
        print(f"Initial Load Result:     {res1['status']} (Record ID: {res1['record_id']})")

        logger.info("Testing duplicate submission...")
        res2 = load_raw_data(test_data)
        print(f"Duplicate Check Result:  {res2['status']} (Record ID: {res2['record_id']}, Inserted: {res2['inserted']})")

        record = get_raw_record(res1["record_id"])
        if record:
            print(f"Preserved Title:         {record['page_title']}")
            print(f"Preserved Headings:      {len(record['headings'])}")
            print(f"Preserved Links:         {len(record['links'])}")

        print("=" * 65)
        print("Phase 3 loading verification completed successfully.")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"Loader verification error: {exc}", file=sys.stderr)
        logger.error(f"Loader verification failed: {exc}", exc_info=True)
        return 1


def run_phase_4_transform() -> int:
    """Run Phase 4 SQL transformation engine on existing raw records."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 4: SQL Transformation Engine")
    print("=" * 65)

    logger = settings.setup_logging()

    try:
        init_db()

        logger.info("Executing SQL transformations on raw records...")
        summary = transform_raw_data()

        print(f"Status:             {summary['status']}")
        print(f"Raw Records Read:   {summary['raw_records_read']}")
        print(f"Records Cleaned:    {summary['records_cleaned']}")
        print(f"Records Inserted:   {summary['records_inserted']}")
        print(f"Duplicates Skipped: {summary['duplicates_skipped']}")
        print(f"Invalid Skipped:    {summary['invalid_records']}")
        print("=" * 65)
        print("Phase 4 transformation completed successfully.")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"Transformation Error: {exc}", file=sys.stderr)
        logger.error(f"Transformation failed: {exc}", exc_info=True)
        return 1


def run_phase_5_pipeline(url: str) -> int:
    """Run the complete end-to-end ELT pipeline for a target website URL (Phase 5)."""
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 5: End-to-End Pipeline Execution")
    print("=" * 65)

    logger = settings.setup_logging()
    logger.info(f"Initiating full ELT pipeline for: {url}")

    summary = run_pipeline(url, extract_fn=extract_page_data)

    if summary["status"] == "SUCCESS":
        ext = summary["extraction"]
        load = summary["loading"]
        trans = summary["transformation"]

        print(f"Run ID:            {summary['run_id']}")
        print(f"Source URL:        {summary['source_url']}")
        print(f"Overall Status:    {summary['status']}")
        print("-" * 65)
        print(" [1/3] EXTRACTION:")
        print(f"   Page Title:       {ext['page_title'] or '(No title found)'}")
        print(f"   Headings Found:   {ext['headings_count']}")
        print(f"   Links Found:      {ext['links_count']}")
        preview = ext['content_preview'] + ("..." if len(ext['content_preview']) >= 200 else "")
        print(f"   Content Preview:  {preview or '(No readable text)'}")
        print("-" * 65)
        print(" [2/3] LOADING (Raw Data):")
        print(f"   Load Status:      {load['status']}")
        print(f"   Raw Record ID:    {load['record_id']}")
        print(f"   Newly Inserted:   {load['inserted']}")
        print("-" * 65)
        print(" [3/3] TRANSFORMATION (SQL):")
        print(f"   Cleaned Records:  {trans['records_cleaned']}")
        print(f"   Transformed Rows: {trans['records_inserted']}")
        print(f"   Duplicates Stored:{trans['duplicates_skipped']}")
        print("=" * 65)
        print("Pipeline execution completed successfully.")
        print("=" * 65)
        return 0
    else:
        err = summary.get("error_message") or "Unknown error"
        failed_stage = summary.get("failed_stage") or "PIPELINE"
        print(f"Pipeline Failed at stage [{failed_stage}]: {err}", file=sys.stderr)
        if failed_stage in ("VALIDATION", "EXTRACTION"):
            print(f"Extraction Error: {err}", file=sys.stderr)
        logger.error(f"Pipeline run #{summary.get('run_id')} failed at [{failed_stage}]: {err}")
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
        help="Target website URL to run through the ELT pipeline (Phase 5).",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract webpage content only without database loading (Phase 2).",
    )
    parser.add_argument(
        "--verify-loader",
        action="store_true",
        help="Verify database loading and duplicate handling with sample data (Phase 3).",
    )
    parser.add_argument(
        "--transform",
        action="store_true",
        help="Execute SQL transformations on raw records (Phase 4).",
    )

    args = parser.parse_args(argv)

    if args.transform:
        return run_phase_4_transform()
    elif args.verify_loader:
        return run_phase_3_verify_loader()
    elif args.url and args.extract_only:
        return run_phase_2_extraction(args.url)
    elif args.url:
        return run_phase_5_pipeline(args.url)
    else:
        return run_phase_1_setup()


if __name__ == "__main__":
    sys.exit(main())
