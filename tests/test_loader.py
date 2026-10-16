"""Unit tests for the database loading module (Phase 3).

Verifies loading of structured extraction data into SQLite, JSON serialization,
preservation of headings and links, validation, deterministic duplicate handling,
and rollback on database errors using temporary databases.
"""

from unittest.mock import MagicMock, patch
import pytest
import sqlite3

from database.connection import get_connection, init_db
from loader.raw_loader import (
    LoaderError,
    LoaderValidationError,
    compute_content_hash,
    get_raw_record,
    load_raw_data,
    sanitize_url_for_logging,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provide a newly initialized temporary SQLite database path."""
    db_path = tmp_path / "test_loader.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def sample_extracted_data():
    """Provide a standard structured extracted data dictionary."""
    return {
        "source_url": "https://example.com/articles/data-engineering",
        "page_title": "Data Engineering Principles",
        "headings": ["Introduction", "ELT Architectures", "Best Practices"],
        "links": [
            {"text": "Home", "url": "https://example.com"},
            {"text": "Documentation", "url": "https://example.com/docs"},
        ],
        "content": "A comprehensive overview of building scalable ELT pipelines using Python and SQLite.",
        "extracted_at": "2026-10-16T14:30:00+00:00",
    }


# =====================================================================
# 1. Successful Insertion & Value Matching Tests
# =====================================================================

def test_valid_record_inserted_successfully(temp_db, sample_extracted_data):
    """Verify that a valid extracted record is loaded and inserted into raw_data."""
    result = load_raw_data(sample_extracted_data, db_path=temp_db)

    assert result["status"] == "INSERTED"
    assert result["inserted"] is True
    assert isinstance(result["record_id"], int)
    assert result["record_id"] > 0
    assert result["source_url"] == sample_extracted_data["source_url"]


def test_inserted_values_match_extracted_values(temp_db, sample_extracted_data):
    """Verify that stored fields accurately match the original extracted data."""
    result = load_raw_data(sample_extracted_data, db_path=temp_db)
    record = get_raw_record(result["record_id"], db_path=temp_db)

    assert record is not None
    assert record["source_url"] == sample_extracted_data["source_url"]
    assert record["page_title"] == sample_extracted_data["page_title"]
    assert record["content"] == sample_extracted_data["content"]
    assert record["extracted_at"] == sample_extracted_data["extracted_at"]
    assert len(record["content_hash"]) == 64  # SHA-256 hex length


def test_headings_and_links_preserved(temp_db, sample_extracted_data):
    """Verify headings and links are serialized and preserved without data loss."""
    result = load_raw_data(sample_extracted_data, db_path=temp_db)
    record = get_raw_record(result["record_id"], db_path=temp_db)

    assert record["headings"] == sample_extracted_data["headings"]
    assert record["links"] == sample_extracted_data["links"]
    assert len(record["headings"]) == 3
    assert len(record["links"]) == 2
    assert record["links"][0]["text"] == "Home"
    assert record["links"][1]["url"] == "https://example.com/docs"


# =====================================================================
# 2. Field Validation & Optional Field Tests
# =====================================================================

@pytest.mark.parametrize("invalid_payload", [
    None,
    "not-a-dict",
    [],
    {"extracted_at": "2026-10-16T12:00:00Z"},  # Missing source_url
    {"source_url": "", "extracted_at": "2026-10-16T12:00:00Z"},  # Empty source_url
    {"source_url": "   ", "extracted_at": "2026-10-16T12:00:00Z"},  # Whitespace source_url
    {"source_url": "https://example.com"},  # Missing extracted_at
    {"source_url": "https://example.com", "extracted_at": ""},  # Empty extracted_at
])
def test_missing_required_fields_rejected(temp_db, invalid_payload):
    """Verify missing, empty, or non-string required fields raise LoaderValidationError."""
    with pytest.raises(LoaderValidationError):
        load_raw_data(invalid_payload, db_path=temp_db)


def test_empty_optional_fields_handled(temp_db):
    """Verify that records with empty/missing optional fields load cleanly with sensible defaults."""
    minimal_data = {
        "source_url": "https://example.com/minimal",
        "extracted_at": "2026-10-16T15:00:00+00:00",
    }
    result = load_raw_data(minimal_data, db_path=temp_db)
    assert result["status"] == "INSERTED"

    record = get_raw_record(result["record_id"], db_path=temp_db)
    assert record["page_title"] == ""
    assert record["headings"] == []
    assert record["links"] == []
    assert record["content"] == ""


# =====================================================================
# 3. Duplicate Handling & Content Update Policy Tests
# =====================================================================

def test_repeated_submissions_do_not_create_duplicates(temp_db, sample_extracted_data):
    """Verify that submitting identical extracted content repeatedly does not create duplicate rows."""
    # First submission
    res1 = load_raw_data(sample_extracted_data, db_path=temp_db)
    assert res1["status"] == "INSERTED"
    assert res1["inserted"] is True

    # Second submission with identical data
    res2 = load_raw_data(sample_extracted_data, db_path=temp_db)
    assert res2["status"] == "DUPLICATE"
    assert res2["inserted"] is False
    assert res2["record_id"] == res1["record_id"]

    # Verify only one row exists in raw_data
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM raw_data WHERE source_url = ?;", (sample_extracted_data["source_url"],))
        assert cursor.fetchone()["total"] == 1
    finally:
        conn.close()


def test_changed_content_stored_as_new_version(temp_db, sample_extracted_data):
    """Verify that when page content changes, the updated version is captured as a new record."""
    # Load version 1
    res1 = load_raw_data(sample_extracted_data, db_path=temp_db)
    assert res1["status"] == "INSERTED"

    # Simulate updated content on a later crawl
    updated_data = dict(sample_extracted_data)
    updated_data["content"] = "Updated page content with new research and statistics."
    updated_data["extracted_at"] = "2026-10-16T18:00:00+00:00"

    res2 = load_raw_data(updated_data, db_path=temp_db)
    assert res2["status"] == "INSERTED"
    assert res2["inserted"] is True
    assert res2["record_id"] != res1["record_id"]

    # Both versions must be preserved in raw_data
    conn = get_connection(temp_db)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, content FROM raw_data WHERE source_url = ? ORDER BY id ASC;",
            (sample_extracted_data["source_url"],),
        )
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0]["id"] == res1["record_id"]
        assert rows[1]["id"] == res2["record_id"]
        assert rows[0]["content"] == sample_extracted_data["content"]
        assert rows[1]["content"] == updated_data["content"]
    finally:
        conn.close()


# =====================================================================
# 4. Transaction Rollback & Error Handling Tests
# =====================================================================

def test_database_failure_triggers_rollback(temp_db, sample_extracted_data):
    """Verify that database errors during insert trigger transaction rollback without corrupting data."""
    with patch("loader.raw_loader.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.OperationalError("Simulated database lock failure")
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_fn.return_value = mock_conn

        with pytest.raises(LoaderError, match="Failed to load raw data into database"):
            load_raw_data(sample_extracted_data, db_path=temp_db)


def test_sanitize_url_for_logging():
    """Verify sensitive query parameters are stripped for safe logging."""
    safe = sanitize_url_for_logging("https://example.com/api?token=secret123&user=admin")
    assert "token" not in safe
    assert "secret123" not in safe
    assert safe == "https://example.com/api?..."
