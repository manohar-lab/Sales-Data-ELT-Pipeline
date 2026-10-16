"""Unit tests for the SQL transformation engine (Phase 4).

Tests data cleaning, whitespace normalization, URL validation, handling of missing/null values,
malformed JSON tolerance, deterministic deduplication, idempotency, incremental runs,
and rollback on database errors using isolated temporary SQLite databases.
"""

from unittest.mock import MagicMock, patch
import pytest
import sqlite3

from database.connection import get_connection, init_db
from loader.raw_loader import load_raw_data
from transformations.transformer import (
    TransformationError,
    get_transformed_records,
    is_valid_source_url,
    normalize_text,
    transform_raw_data,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provide a newly initialized temporary SQLite database path."""
    db_path = tmp_path / "test_transformer.db"
    init_db(db_path)
    return db_path


def insert_raw_record(
    db_path,
    source_url="https://example.com/test",
    page_title="Test Title",
    headings='["Heading 1", "Heading 2"]',
    links='[{"text": "Link", "url": "https://example.com/link"}]',
    content="This is meaningful test content for transformation.",
    extracted_at="2026-10-16T12:00:00+00:00",
):
    """Insert a record directly into raw_data for testing."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO raw_data (
                    source_url, page_title, headings, links, content, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (source_url, page_title, headings, links, content, extracted_at),
            )
            return cursor.lastrowid
    finally:
        conn.close()


# =====================================================================
# 1. Successful Transformation & Normalization Tests
# =====================================================================

def test_valid_raw_record_transformed_successfully(temp_db):
    """Verify that a valid raw record is cleaned and inserted into transformed_data."""
    raw_id = insert_raw_record(temp_db)
    summary = transform_raw_data(temp_db)

    assert summary["status"] == "SUCCESS"
    assert summary["raw_records_read"] == 1
    assert summary["records_inserted"] == 1
    assert summary["valid_records"] == 1

    records = get_transformed_records(temp_db)
    assert len(records) == 1
    rec = records[0]
    assert rec["raw_id"] == raw_id
    assert rec["source_url"] == "https://example.com/test"
    assert rec["page_title"] == "Test Title"
    assert rec["content"] == "This is meaningful test content for transformation."
    assert rec["headings"] == ["Heading 1", "Heading 2"]
    assert rec["links"] == [{"text": "Link", "url": "https://example.com/link"}]
    assert len(rec["content_hash"]) == 64
    assert "T" in rec["transformed_at"]


def test_whitespace_cleaning_and_normalization(temp_db):
    """Verify leading/trailing whitespace is stripped and internal whitespace normalized."""
    insert_raw_record(
        temp_db,
        page_title="   Messy    Title   With   Spaces   ",
        content="   First  paragraph   \n\t  with   extra   spacing.   ",
    )
    transform_raw_data(temp_db)

    records = get_transformed_records(temp_db)
    assert len(records) == 1
    assert records[0]["page_title"] == "Messy Title With Spaces"
    assert records[0]["content"] == "First paragraph with extra spacing."


def test_empty_strings_and_null_values(temp_db):
    """Verify empty or whitespace-only titles are stored as NULL (None)."""
    insert_raw_record(
        temp_db,
        page_title="     ",
        content="Valid content with blank title",
    )
    transform_raw_data(temp_db)

    records = get_transformed_records(temp_db)
    assert len(records) == 1
    assert records[0]["page_title"] is None
    assert records[0]["content"] == "Valid content with blank title"


def test_missing_title_does_not_reject_useful_content(temp_db):
    """Verify records with missing titles are transformed if usable content exists."""
    insert_raw_record(
        temp_db,
        page_title=None,
        content="Useful article content with no title provided.",
    )
    summary = transform_raw_data(temp_db)

    assert summary["records_inserted"] == 1
    assert summary["invalid_records"] == 0


def test_record_without_meaningful_content_rejected(temp_db):
    """Verify records with empty/whitespace content and no headings are rejected."""
    insert_raw_record(
        temp_db,
        page_title="Title Only",
        headings=None,
        content="    \n   ",
    )
    summary = transform_raw_data(temp_db)

    assert summary["records_inserted"] == 0
    assert summary["invalid_records"] == 1
    assert summary["records_skipped"] == 1


def test_invalid_source_url_rejected(temp_db):
    """Verify raw records with invalid URL schemes or embedded credentials are rejected."""
    insert_raw_record(
        temp_db,
        source_url="ftp://example.com/file",
        content="Valid content but invalid scheme",
    )
    insert_raw_record(
        temp_db,
        source_url="http://user:pass@example.com",
        content="Valid content but embedded credentials",
    )
    summary = transform_raw_data(temp_db)

    assert summary["records_inserted"] == 0
    assert summary["invalid_records"] == 2


def test_headings_and_links_preserved(temp_db):
    """Verify structured headings and links are properly preserved in transformed records."""
    insert_raw_record(
        temp_db,
        headings='["Overview", "Architecture", "Conclusion"]',
        links='[{"text": "Docs", "url": "https://example.com/docs"}]',
    )
    transform_raw_data(temp_db)

    records = get_transformed_records(temp_db)
    assert records[0]["headings"] == ["Overview", "Architecture", "Conclusion"]
    assert records[0]["links"] == [{"text": "Docs", "url": "https://example.com/docs"}]


def test_malformed_optional_json_handled_safely(temp_db):
    """Verify malformed JSON in headings or links does not crash the transformation run."""
    insert_raw_record(
        temp_db,
        headings="<<bad-json>>",
        links="{not a list}",
        content="Valid readable article content.",
    )
    summary = transform_raw_data(temp_db)

    assert summary["status"] == "SUCCESS"
    assert summary["records_inserted"] == 1

    records = get_transformed_records(temp_db)
    assert records[0]["headings"] == []
    assert records[0]["links"] == []
    assert records[0]["content"] == "Valid readable article content."


# =====================================================================
# 2. Deduplication & Idempotency Tests
# =====================================================================

def test_exact_duplicates_handled_deterministically(temp_db):
    """Verify that identical raw records result in only one transformed record."""
    # Insert two identical raw records
    insert_raw_record(temp_db, content="Identical content snapshot.")
    insert_raw_record(temp_db, content="Identical content snapshot.")

    summary = transform_raw_data(temp_db)
    assert summary["raw_records_read"] == 2
    assert summary["records_inserted"] == 1
    assert summary["duplicates_skipped"] == 1

    records = get_transformed_records(temp_db)
    assert len(records) == 1


def test_distinct_content_from_same_url_preserved(temp_db):
    """Verify distinct content snapshots from the same URL are both preserved."""
    insert_raw_record(temp_db, source_url="https://example.com", content="Version 1 content.")
    insert_raw_record(temp_db, source_url="https://example.com", content="Version 2 content updated.")

    summary = transform_raw_data(temp_db)
    assert summary["raw_records_read"] == 2
    assert summary["records_inserted"] == 2
    assert summary["duplicates_skipped"] == 0

    records = get_transformed_records(temp_db)
    assert len(records) == 2


def test_repeated_transformation_runs_do_not_create_duplicate_output(temp_db):
    """Verify idempotency: running transformation multiple times does not insert duplicates."""
    insert_raw_record(temp_db, content="Test content for idempotency.")

    # Run 1
    summary1 = transform_raw_data(temp_db)
    assert summary1["records_inserted"] == 1
    assert summary1["duplicates_skipped"] == 0

    # Run 2 on unchanged data
    summary2 = transform_raw_data(temp_db)
    assert summary2["records_inserted"] == 0
    assert summary2["duplicates_skipped"] == 1

    records = get_transformed_records(temp_db)
    assert len(records) == 1


def test_new_raw_records_processed_on_subsequent_runs(temp_db):
    """Verify incremental processing: newly loaded raw records are processed in later runs."""
    insert_raw_record(temp_db, source_url="https://example.com/1", content="Page 1")
    transform_raw_data(temp_db)

    # Insert a new raw record
    insert_raw_record(temp_db, source_url="https://example.com/2", content="Page 2")
    summary = transform_raw_data(temp_db)

    assert summary["raw_records_read"] == 2
    assert summary["records_inserted"] == 1
    assert summary["duplicates_skipped"] == 1

    records = get_transformed_records(temp_db)
    assert len(records) == 2


def test_raw_records_remain_unchanged(temp_db):
    """Verify that transformation leaves the raw_data table completely unmodified."""
    raw_id = insert_raw_record(
        temp_db,
        source_url="https://example.com/clean",
        page_title="  Raw Title  ",
        content="  Raw Content  ",
    )

    transform_raw_data(temp_db)

    # Inspect raw_data
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM raw_data WHERE id = ?;", (raw_id,))
        raw = cursor.fetchone()
        assert raw["page_title"] == "  Raw Title  "  # Whitespace still intact in raw_data
        assert raw["content"] == "  Raw Content  "
    finally:
        conn.close()


# =====================================================================
# 3. Transaction Rollback & Summary Metric Tests
# =====================================================================

def test_database_failure_rolls_back_changes(temp_db):
    """Verify that a database error during transformation rolls back the transaction."""
    insert_raw_record(temp_db, content="Content to be rolled back.")

    with patch("transformations.transformer.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Allow SELECT from raw_data, but fail on INSERT into transformed_data
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "source_url": "https://example.com",
                "page_title": "Title",
                "headings": "[]",
                "links": "[]",
                "content": "Content",
                "extracted_at": "2026-10-16T12:00:00Z",
            }
        ]
        # First execute is the SELECT (succeeds), second is the duplicate check (succeeds), third is INSERT (fails)
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.side_effect = [
            None,  # SELECT raw_data
            None,  # SELECT duplicate check
            sqlite3.OperationalError("Simulated write failure"),
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_fn.return_value = mock_conn

        with pytest.raises(TransformationError, match="Database transaction failed"):
            transform_raw_data(temp_db)


def test_transformation_summary_counts_match_actual_results(temp_db):
    """Verify transformation summary counts accurately reflect the operations performed."""
    insert_raw_record(temp_db, source_url="https://example.com/1", content="Valid 1")
    insert_raw_record(temp_db, source_url="https://example.com/1", content="Valid 1")  # Duplicate
    insert_raw_record(temp_db, source_url="ftp://invalid-url.com", content="Valid content")  # Invalid URL
    insert_raw_record(temp_db, source_url="https://example.com/3", content="   ", headings=None)  # No usable content

    summary = transform_raw_data(temp_db)

    assert summary["raw_records_read"] == 4
    assert summary["records_cleaned"] == 2  # The 2 valid ones
    assert summary["records_inserted"] == 1
    assert summary["duplicates_skipped"] == 1
    assert summary["invalid_records"] == 2
    assert summary["records_skipped"] == 3  # 1 duplicate + 2 invalid
