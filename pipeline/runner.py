"""End-to-end ELT Pipeline Runner for the Website-to-Database ELT Pipeline (Phase 5).

Coordinates the three-stage ELT workflow:
    1. Extract: Fetch and parse webpage HTML into structured records.
    2. Load: Persist raw extracted data into SQLite raw_data.
    3. Transform: Clean, normalize, and populate transformed_data using SQL.

Tracks execution metadata, timestamps, record counts, and errors in pipeline_runs.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
from typing import Any, Callable, Optional

from config import settings
from database.connection import get_connection, init_db
from extractor.scraper import (
    ExtractionError,
    URLValidationError,
    extract_page_data,
    validate_url,
)
from loader.raw_loader import (
    LoaderError,
    load_raw_data,
    sanitize_url_for_logging,
)
from transformations.transformer import (
    TransformationError,
    transform_raw_data,
)

logger = logging.getLogger("elt_pipeline")


# =====================================================================
# Custom Exceptions
# =====================================================================

class PipelineError(Exception):
    """Raised when an error occurs during end-to-end pipeline execution."""

    def __init__(self, message: str, stage: str, summary: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.stage = stage
        self.summary = summary or {}


# =====================================================================
# Pipeline Runs Tracking Helpers
# =====================================================================

def record_run_start(
    source_url: str,
    started_at: str,
    db_path: Optional[Path | str] = None,
) -> int:
    """Insert a new entry with RUNNING status into pipeline_runs.

    Args:
        source_url: Target website URL.
        started_at: ISO 8601 UTC timestamp.
        db_path: Optional SQLite database file path.

    Returns:
        int: The newly created run_id primary key.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_runs (
                    source_url,
                    started_at,
                    completed_at,
                    status,
                    records_extracted,
                    error_message
                ) VALUES (?, ?, NULL, 'RUNNING', 0, NULL);
                """,
                (source_url, started_at),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def update_run_completion(
    run_id: int,
    status: str,
    completed_at: str,
    records_extracted: int,
    error_message: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> None:
    """Update pipeline_runs entry with final status, completion time, and error details.

    Args:
        run_id: Pipeline run primary key ID.
        status: Final status ('SUCCESS' or 'FAILED').
        completed_at: ISO 8601 UTC timestamp.
        records_extracted: Total records extracted.
        error_message: Error description if failed.
        db_path: Optional SQLite database path.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE pipeline_runs
                SET status = ?,
                    completed_at = ?,
                    records_extracted = ?,
                    error_message = ?
                WHERE run_id = ?;
                """,
                (status, completed_at, records_extracted, error_message, run_id),
            )
    finally:
        conn.close()


def get_pipeline_run(
    run_id: int,
    db_path: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Retrieve a single pipeline_runs record by ID.

    Args:
        run_id: Pipeline run ID.
        db_path: Optional SQLite database path.

    Returns:
        dict: The run record or None if not found.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pipeline_runs WHERE run_id = ?;", (run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# =====================================================================
# Main Pipeline Orchestrator
# =====================================================================

def run_pipeline(
    url: str,
    db_path: Optional[Path | str] = None,
    extract_fn: Optional[Callable] = None,
    load_fn: Optional[Callable] = None,
    transform_fn: Optional[Callable] = None,
) -> dict[str, Any]:
    """Execute the complete end-to-end ELT pipeline for a target website URL.

    Workflow:
        1. Validate URL.
        2. Record run start in pipeline_runs ('RUNNING').
        3. Extract webpage data using Beautiful Soup / Requests.
        4. Load raw extracted data into SQLite raw_data.
        5. Transform raw data into structured analysis-ready records using SQL.
        6. Record completion status in pipeline_runs ('SUCCESS' or 'FAILED').

    Args:
        url: Target website URL.
        db_path: Optional SQLite database path override (for test isolation).
        extract_fn: Optional extractor callable (defaults to extract_page_data).
        load_fn: Optional loader callable (defaults to load_raw_data).
        transform_fn: Optional transformer callable (defaults to transform_raw_data).

    Returns:
        dict: Comprehensive execution summary.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    settings.init_directories()
    init_db(target_db)

    started_at = datetime.now(timezone.utc).isoformat()
    safe_url = sanitize_url_for_logging(url)

    # Initialize execution summary structure
    summary: dict[str, Any] = {
        "status": "RUNNING",
        "run_id": None,
        "source_url": url,
        "started_at": started_at,
        "completed_at": None,
        "failed_stage": None,
        "records_extracted": 0,
        "extraction": {},
        "loading": {},
        "transformation": {},
        "error_message": None,
    }

    # Record initial run in database
    run_id = record_run_start(url, started_at, target_db)
    summary["run_id"] = run_id
    logger.info(f"Pipeline run #{run_id} started for: {safe_url}")

    # -----------------------------------------------------------------
    # Stage 1: Extraction (includes URL validation via extractor)
    # -----------------------------------------------------------------
    extractor = extract_fn or extract_page_data
    logger.info(f"Pipeline run #{run_id}: [1/3] Extracting webpage data...")

    try:
        extracted_data = extractor(url)
        if not isinstance(extracted_data, dict) or not extracted_data.get("source_url"):
            raise ExtractionError("Extraction returned empty or invalid data payload.")
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        err_msg = str(exc)
        logger.error(f"Pipeline run #{run_id} failed during extraction: {err_msg}")
        update_run_completion(run_id, "FAILED", completed_at, 0, err_msg, target_db)

        summary["status"] = "FAILED"
        summary["completed_at"] = completed_at
        summary["failed_stage"] = "EXTRACTION"
        summary["error_message"] = err_msg
        return summary

    summary["records_extracted"] = 1
    summary["extraction"] = {
        "status": "SUCCESS",
        "page_title": extracted_data.get("page_title") or "",
        "headings_count": len(extracted_data.get("headings") or []),
        "links_count": len(extracted_data.get("links") or []),
        "content_preview": (extracted_data.get("content") or "")[:200],
    }

    # -----------------------------------------------------------------
    # Stage 2: Loading (Raw Data)
    # -----------------------------------------------------------------
    loader = load_fn or load_raw_data
    logger.info(f"Pipeline run #{run_id}: [2/3] Loading raw data into SQLite...")

    try:
        load_result = loader(extracted_data, db_path=target_db)
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        err_msg = str(exc)
        logger.error(f"Pipeline run #{run_id} failed during loading: {err_msg}")
        update_run_completion(run_id, "FAILED", completed_at, 1, err_msg, target_db)

        summary["status"] = "FAILED"
        summary["completed_at"] = completed_at
        summary["failed_stage"] = "LOADING"
        summary["error_message"] = err_msg
        return summary

    summary["loading"] = {
        "status": load_result["status"],
        "record_id": load_result["record_id"],
        "inserted": load_result["inserted"],
        "message": load_result["message"],
    }

    # -----------------------------------------------------------------
    # Stage 3: Transformation (SQL)
    # -----------------------------------------------------------------
    transformer = transform_fn or transform_raw_data
    logger.info(f"Pipeline run #{run_id}: [3/3] Transforming data using SQL...")

    try:
        transform_result = transformer(db_path=target_db)
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        err_msg = str(exc)
        logger.error(f"Pipeline run #{run_id} failed during transformation: {err_msg}")
        update_run_completion(run_id, "FAILED", completed_at, 1, err_msg, target_db)

        summary["status"] = "FAILED"
        summary["completed_at"] = completed_at
        summary["failed_stage"] = "TRANSFORMATION"
        summary["error_message"] = err_msg
        return summary

    summary["transformation"] = {
        "status": transform_result["status"],
        "records_cleaned": transform_result["records_cleaned"],
        "records_inserted": transform_result["records_inserted"],
        "duplicates_skipped": transform_result["duplicates_skipped"],
        "invalid_records": transform_result["invalid_records"],
    }

    # -----------------------------------------------------------------
    # Pipeline Completion
    # -----------------------------------------------------------------
    completed_at = datetime.now(timezone.utc).isoformat()
    update_run_completion(run_id, "SUCCESS", completed_at, 1, None, target_db)

    summary["status"] = "SUCCESS"
    summary["completed_at"] = completed_at
    logger.info(f"Pipeline run #{run_id} completed successfully for: {safe_url}")

    return summary
