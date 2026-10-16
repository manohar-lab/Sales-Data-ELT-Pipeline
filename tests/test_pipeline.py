"""Integration tests for the end-to-end ELT Pipeline (Phase 5).

Tests end-to-end orchestration: Extract -> Load Raw Data -> Transform Using SQL.
Verifies pipeline_runs tracking (RUNNING, SUCCESS, FAILED), stage failure halts,
duplicate handling, raw data preservation on transformation failures,
and database metric consistency without external network access.
"""

from unittest.mock import MagicMock, patch
import pytest
import sqlite3

from database.connection import get_connection, init_db
from extractor.scraper import RequestError, URLValidationError
from loader.raw_loader import LoaderError
from pipeline.runner import get_pipeline_run, run_pipeline
from transformations.transformer import TransformationError
import main


@pytest.fixture
def temp_db(tmp_path):
    """Provide a newly initialized isolated temporary SQLite database path."""
    db_path = tmp_path / "test_pipeline.db"
    init_db(db_path)
    return db_path


SAMPLE_EXTRACTED_DATA = {
    "source_url": "https://example.com/pipeline-article",
    "page_title": "End-to-End Pipeline Principles",
    "headings": ["Overview", "Extraction Stage", "Loading Stage", "Transformation Stage"],
    "links": [
        {"text": "Docs", "url": "https://example.com/docs"},
        {"text": "GitHub", "url": "https://github.com/manohar-lab"},
    ],
    "content": "A unified ELT pipeline seamlessly automates web data extraction, raw persistence, and SQL transformation.",
    "extracted_at": "2026-10-16T12:00:00+00:00",
}


# =====================================================================
# 1. Successful End-to-End Workflow Tests
# =====================================================================

def test_pipeline_successful_end_to_end_run(temp_db):
    """Verify complete Extract -> Load -> Transform execution and history tracking."""
    with patch("pipeline.runner.extract_page_data", return_value=SAMPLE_EXTRACTED_DATA):
        summary = run_pipeline("https://example.com/pipeline-article", db_path=temp_db)

    assert summary["status"] == "SUCCESS"
    assert summary["records_extracted"] == 1
    assert summary["extraction"]["status"] == "SUCCESS"
    assert summary["loading"]["status"] == "INSERTED"
    assert summary["loading"]["inserted"] is True
    assert summary["transformation"]["status"] == "SUCCESS"
    assert summary["transformation"]["records_inserted"] == 1

    # Verify pipeline_runs entry
    run_entry = get_pipeline_run(summary["run_id"], db_path=temp_db)
    assert run_entry is not None
    assert run_entry["status"] == "SUCCESS"
    assert run_entry["source_url"] == "https://example.com/pipeline-article"
    assert run_entry["records_extracted"] == 1
    assert run_entry["error_message"] is None
    assert run_entry["started_at"] is not None
    assert run_entry["completed_at"] is not None

    # Verify raw_data has 1 record
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM raw_data;")
        assert cursor.fetchone()["total"] == 1

        # Verify transformed_data has 1 record
        cursor.execute("SELECT COUNT(*) AS total FROM transformed_data;")
        assert cursor.fetchone()["total"] == 1
    finally:
        conn.close()


# =====================================================================
# 2. Stage Failure & Dependent Stage Halt Tests
# =====================================================================

def test_pipeline_invalid_url_handling(temp_db):
    """Verify invalid URL fails gracefully, records FAILED in history, and halts pipeline."""
    summary = run_pipeline("ftp://unsupported-scheme.com", db_path=temp_db)

    assert summary["status"] == "FAILED"
    assert summary["failed_stage"] == "EXTRACTION"
    assert summary["records_extracted"] == 0
    assert "Unsupported URL scheme" in summary["error_message"]

    run_entry = get_pipeline_run(summary["run_id"], db_path=temp_db)
    assert run_entry["status"] == "FAILED"
    assert run_entry["records_extracted"] == 0
    assert "Unsupported URL scheme" in run_entry["error_message"]

    # Verify no raw or transformed records created
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM raw_data;")
        assert cursor.fetchone()["total"] == 0
        cursor.execute("SELECT COUNT(*) AS total FROM transformed_data;")
        assert cursor.fetchone()["total"] == 0
    finally:
        conn.close()


def test_pipeline_extraction_failure_halts_pipeline(temp_db):
    """Verify extraction failure halts execution before loading or transformation."""
    mock_extractor = MagicMock(side_effect=RequestError("HTTP request failed: 404 Not Found"))
    mock_loader = MagicMock()
    mock_transformer = MagicMock()

    summary = run_pipeline(
        "https://example.com/not-found",
        db_path=temp_db,
        extract_fn=mock_extractor,
        load_fn=mock_loader,
        transform_fn=mock_transformer,
    )

    assert summary["status"] == "FAILED"
    assert summary["failed_stage"] == "EXTRACTION"
    assert "404 Not Found" in summary["error_message"]

    # Dependent stages must not have been executed
    mock_loader.assert_not_called()
    mock_transformer.assert_not_called()

    run_entry = get_pipeline_run(summary["run_id"], db_path=temp_db)
    assert run_entry["status"] == "FAILED"
    assert run_entry["records_extracted"] == 0


def test_pipeline_loading_failure_halts_pipeline(temp_db):
    """Verify loading failure records extracted count, halts transformation, and marks FAILED."""
    mock_extractor = MagicMock(return_value=SAMPLE_EXTRACTED_DATA)
    mock_loader = MagicMock(side_effect=LoaderError("Database disk full error"))
    mock_transformer = MagicMock()

    summary = run_pipeline(
        "https://example.com/pipeline-article",
        db_path=temp_db,
        extract_fn=mock_extractor,
        load_fn=mock_loader,
        transform_fn=mock_transformer,
    )

    assert summary["status"] == "FAILED"
    assert summary["failed_stage"] == "LOADING"
    assert "Database disk full" in summary["error_message"]

    # Transformation must not have been executed
    mock_transformer.assert_not_called()

    run_entry = get_pipeline_run(summary["run_id"], db_path=temp_db)
    assert run_entry["status"] == "FAILED"
    assert run_entry["records_extracted"] == 1  # Extraction succeeded before loading failed


def test_pipeline_transformation_failure_preserves_raw_data(temp_db):
    """Verify that transformation failure preserves raw data while marking run FAILED."""
    mock_extractor = MagicMock(return_value=SAMPLE_EXTRACTED_DATA)
    mock_transformer = MagicMock(side_effect=TransformationError("SQL syntax failure"))

    summary = run_pipeline(
        "https://example.com/pipeline-article",
        db_path=temp_db,
        extract_fn=mock_extractor,
        transform_fn=mock_transformer,
    )

    assert summary["status"] == "FAILED"
    assert summary["failed_stage"] == "TRANSFORMATION"
    assert "SQL syntax failure" in summary["error_message"]

    # Verify raw data was preserved despite transformation error
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM raw_data;")
        assert cursor.fetchone()["total"] == 1

        cursor.execute("SELECT COUNT(*) AS total FROM transformed_data;")
        assert cursor.fetchone()["total"] == 0
    finally:
        conn.close()

    run_entry = get_pipeline_run(summary["run_id"], db_path=temp_db)
    assert run_entry["status"] == "FAILED"


# =====================================================================
# 3. Duplicate Handling & Idempotent Transformation Tests
# =====================================================================

def test_pipeline_duplicate_submissions_handled_properly(temp_db):
    """Verify repeated runs of the same URL respect loader duplicate policy without duplicate transforms."""
    with patch("pipeline.runner.extract_page_data", return_value=SAMPLE_EXTRACTED_DATA):
        # Run 1
        summary1 = run_pipeline("https://example.com/pipeline-article", db_path=temp_db)
        assert summary1["status"] == "SUCCESS"
        assert summary1["loading"]["status"] == "INSERTED"
        assert summary1["transformation"]["records_inserted"] == 1

        # Run 2 with identical content
        summary2 = run_pipeline("https://example.com/pipeline-article", db_path=temp_db)
        assert summary2["status"] == "SUCCESS"
        assert summary2["loading"]["status"] == "DUPLICATE"
        assert summary2["loading"]["inserted"] is False
        assert summary2["transformation"]["records_inserted"] == 0
        assert summary2["transformation"]["duplicates_skipped"] == 1

    # Database verification: exactly 1 raw and 1 transformed record
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM raw_data;")
        assert cursor.fetchone()["total"] == 1

        cursor.execute("SELECT COUNT(*) AS total FROM transformed_data;")
        assert cursor.fetchone()["total"] == 1

        # 2 distinct pipeline run history entries recorded
        cursor.execute("SELECT COUNT(*) AS total FROM pipeline_runs;")
        assert cursor.fetchone()["total"] == 2
    finally:
        conn.close()


# =====================================================================
# 4. CLI Full Pipeline Verification
# =====================================================================

def test_cli_full_pipeline_success(capsys, temp_db):
    """Verify CLI --url command executes the full pipeline and displays stage summaries."""
    with patch("main.run_pipeline") as mock_runner:
        mock_runner.return_value = {
            "status": "SUCCESS",
            "run_id": 42,
            "source_url": "https://example.com/test",
            "started_at": "2026-10-16T12:00:00Z",
            "completed_at": "2026-10-16T12:00:05Z",
            "extraction": {
                "status": "SUCCESS",
                "page_title": "CLI Test Article",
                "headings_count": 3,
                "links_count": 5,
                "content_preview": "Readable excerpt for CLI verification.",
            },
            "loading": {
                "status": "INSERTED",
                "record_id": 1,
                "inserted": True,
            },
            "transformation": {
                "status": "SUCCESS",
                "records_cleaned": 1,
                "records_inserted": 1,
                "duplicates_skipped": 0,
            },
        }

        exit_code = main.main(["--url", "https://example.com/test"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Phase 5: End-to-End Pipeline Execution" in captured.out
        assert "[1/3] EXTRACTION:" in captured.out
        assert "CLI Test Article" in captured.out
        assert "[2/3] LOADING (Raw Data):" in captured.out
        assert "Raw Record ID:    1" in captured.out
        assert "[3/3] TRANSFORMATION (SQL):" in captured.out
        assert "Transformed Rows: 1" in captured.out
