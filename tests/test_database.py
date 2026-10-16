"""Unit tests for SQLite database connectivity and schema initialization.

Verifies table creation, idempotency, row factory configuration, and column definitions
using temporary isolated databases without external network dependencies.
"""

import sqlite3
import pytest
from database.connection import get_connection, init_db


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a path to a temporary database file in an isolated directory."""
    return tmp_path / "test_pipeline.db"


def test_sqlite_row_factory(temp_db_path):
    """Verify that get_connection configures sqlite3.Row as the row factory."""
    conn = get_connection(temp_db_path)
    try:
        assert conn.row_factory == sqlite3.Row

        # Verify column name access using a sample query
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS id, 'sample_data' AS value")
        row = cursor.fetchone()
        assert row is not None
        assert row["id"] == 1
        assert row["value"] == "sample_data"
        assert row[0] == 1
        assert row[1] == "sample_data"
    finally:
        conn.close()


def test_database_initialization_succeeds(temp_db_path):
    """Verify that database initialization successfully creates the database file."""
    assert not temp_db_path.exists()
    init_db(temp_db_path)
    assert temp_db_path.exists()


def test_expected_tables_exist(temp_db_path):
    """Verify that raw_data, transformed_data, and pipeline_runs tables exist."""
    init_db(temp_db_path)

    conn = get_connection(temp_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

        expected_tables = {"raw_data", "transformed_data", "pipeline_runs"}
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
    finally:
        conn.close()


def test_schema_initialization_is_idempotent(temp_db_path):
    """Verify that init_db can be executed multiple times safely without errors."""
    # First execution
    init_db(temp_db_path)
    # Second execution should be safe and error-free
    init_db(temp_db_path)

    conn = get_connection(temp_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

        expected_tables = {"raw_data", "transformed_data", "pipeline_runs"}
        assert expected_tables.issubset(tables)
    finally:
        conn.close()


def test_table_columns_and_definitions(temp_db_path):
    """Verify that all three tables have the expected columns."""
    init_db(temp_db_path)

    conn = get_connection(temp_db_path)
    try:
        cursor = conn.cursor()

        # Check raw_data columns
        cursor.execute("PRAGMA table_info(raw_data);")
        raw_columns = {row["name"] for row in cursor.fetchall()}
        expected_raw = {"id", "source_url", "page_title", "content", "extracted_at"}
        assert expected_raw.issubset(raw_columns), f"raw_data missing: {expected_raw - raw_columns}"

        # Check transformed_data columns
        cursor.execute("PRAGMA table_info(transformed_data);")
        transformed_columns = {row["name"] for row in cursor.fetchall()}
        expected_transformed = {"id", "source_url", "page_title", "content", "transformed_at"}
        assert expected_transformed.issubset(transformed_columns), (
            f"transformed_data missing: {expected_transformed - transformed_columns}"
        )

        # Check pipeline_runs columns
        cursor.execute("PRAGMA table_info(pipeline_runs);")
        runs_columns = {row["name"] for row in cursor.fetchall()}
        expected_runs = {
            "run_id",
            "source_url",
            "started_at",
            "completed_at",
            "status",
            "records_extracted",
            "error_message",
        }
        assert expected_runs.issubset(runs_columns), (
            f"pipeline_runs missing: {expected_runs - runs_columns}"
        )
    finally:
        conn.close()


def test_initial_database_has_no_fabricated_records(temp_db_path):
    """Verify that newly initialized tables are completely empty without mock data."""
    init_db(temp_db_path)

    conn = get_connection(temp_db_path)
    try:
        cursor = conn.cursor()
        for table_name in ["raw_data", "transformed_data", "pipeline_runs"]:
            cursor.execute(f"SELECT COUNT(*) AS total FROM {table_name};")
            row = cursor.fetchone()
            assert row["total"] == 0, f"Table {table_name} must contain no initial records."
    finally:
        conn.close()
