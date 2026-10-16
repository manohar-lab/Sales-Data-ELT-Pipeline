"""Database loading module for the Website-to-Database ELT Pipeline (Phase 3).

Persists structured webpage data produced by the extraction engine into SQLite raw_data.
Implements deterministic duplicate detection, transaction rollback, and secure logging.
"""

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Optional
import urllib.parse

from config import settings
from database.connection import get_connection

logger = logging.getLogger("elt_pipeline")


# =====================================================================
# Custom Exceptions
# =====================================================================

class LoaderError(Exception):
    """Base exception for database loading failures."""
    pass


class LoaderValidationError(LoaderError):
    """Raised when extracted data fails validation before loading."""
    pass


# =====================================================================
# Helpers
# =====================================================================

def sanitize_url_for_logging(url: str) -> str:
    """Return URL without sensitive query parameters for clean logging."""
    try:
        parsed = urllib.parse.urlsplit(url)
        # Log scheme, host, and path; redact query string if present
        query_indicator = "?..." if parsed.query else ""
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{query_indicator}"
    except Exception:
        return "<invalid-url>"


def compute_content_hash(
    source_url: str,
    page_title: str,
    headings_json: str,
    links_json: str,
    content: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint of the extracted data.

    Used to detect unchanged duplicate submissions while permitting new versions
    to be stored when content changes over time.
    """
    hasher = hashlib.sha256()
    hasher.update(source_url.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update((page_title or "").strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update(headings_json.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(links_json.encode("utf-8"))
    hasher.update(b"|")
    hasher.update((content or "").strip().encode("utf-8"))
    return hasher.hexdigest()


def validate_extracted_data(data: Any) -> None:
    """Validate that extracted data contains required fields with non-empty values.

    Args:
        data: The dictionary returned by the scraper.

    Raises:
        LoaderValidationError: If required fields are missing, invalid, or empty.
    """
    if not isinstance(data, dict):
        raise LoaderValidationError(f"Expected extracted data as dict, got {type(data).__name__}.")

    # Required fields
    source_url = data.get("source_url")
    if not source_url or not isinstance(source_url, str) or not source_url.strip():
        raise LoaderValidationError("Missing or invalid required field 'source_url'.")

    extracted_at = data.get("extracted_at")
    if not extracted_at or not isinstance(extracted_at, str) or not extracted_at.strip():
        raise LoaderValidationError("Missing or invalid required field 'extracted_at'.")


# =====================================================================
# Main Loading Function
# =====================================================================

def load_raw_data(
    extracted_data: dict[str, Any],
    db_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Load extracted structured data into the raw_data SQLite table.

    Validates required fields, serializes complex fields (headings, links) to JSON,
    generates a deterministic SHA-256 fingerprint, and checks for existing duplicate records.
    If an identical record already exists, duplicate insertion is avoided. If the page
    content has changed, the new version is recorded.

    Args:
        extracted_data: Dictionary containing:
            - source_url (str, required)
            - extracted_at (str, required)
            - page_title (str, optional)
            - headings (list[str], optional)
            - links (list[dict], optional)
            - content (str, optional)
        db_path: Optional SQLite database file path override.

    Returns:
        dict: Operation summary containing:
            - status (str): "INSERTED" or "DUPLICATE"
            - record_id (int): Database primary key ID
            - source_url (str): The target URL
            - content_hash (str): Deterministic fingerprint
            - inserted (bool): True if newly inserted, False if duplicate
            - message (str): Human-readable outcome description

    Raises:
        LoaderValidationError: If required fields are missing or invalid.
        LoaderError: If a database error occurs during the transaction.
    """
    validate_extracted_data(extracted_data)

    source_url = extracted_data["source_url"].strip()
    extracted_at = extracted_data["extracted_at"].strip()
    page_title = (extracted_data.get("page_title") or "").strip()
    content = (extracted_data.get("content") or "").strip()

    headings = extracted_data.get("headings") or []
    if not isinstance(headings, list):
        headings = [str(headings)]

    links = extracted_data.get("links") or []
    if not isinstance(links, list):
        links = [links]

    # Deterministic JSON serialization
    headings_json = json.dumps(headings, ensure_ascii=False, sort_keys=True)
    links_json = json.dumps(links, ensure_ascii=False, sort_keys=True)

    content_hash = compute_content_hash(
        source_url=source_url,
        page_title=page_title,
        headings_json=headings_json,
        links_json=links_json,
        content=content,
    )

    safe_url = sanitize_url_for_logging(source_url)
    logger.info(f"Loading raw data for: {safe_url}")

    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)

    try:
        with conn:
            cursor = conn.cursor()

            # Duplicate check: check if exact identical record already exists
            cursor.execute(
                "SELECT id FROM raw_data WHERE source_url = ? AND content_hash = ? ORDER BY id DESC LIMIT 1;",
                (source_url, content_hash),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                existing_id = existing_row["id"]
                logger.info(
                    f"Duplicate raw record detected for {safe_url} (existing record ID: {existing_id}). Insertion skipped."
                )
                return {
                    "status": "DUPLICATE",
                    "record_id": existing_id,
                    "source_url": source_url,
                    "content_hash": content_hash,
                    "inserted": False,
                    "message": f"Identical record already exists for {source_url} (ID: {existing_id}).",
                }

            # Insert new record using parameterized SQL
            cursor.execute(
                """
                INSERT INTO raw_data (
                    source_url,
                    page_title,
                    headings,
                    links,
                    content,
                    content_hash,
                    extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    source_url,
                    page_title,
                    headings_json,
                    links_json,
                    content,
                    content_hash,
                    extracted_at,
                ),
            )
            record_id = cursor.lastrowid
            logger.info(f"Inserted new raw record for {safe_url} (record ID: {record_id}).")

            return {
                "status": "INSERTED",
                "record_id": record_id,
                "source_url": source_url,
                "content_hash": content_hash,
                "inserted": True,
                "message": f"Successfully loaded raw record for {source_url} (ID: {record_id}).",
            }

    except sqlite3.Error as exc:
        logger.error(f"Database error while loading raw data for {safe_url}: {exc}")
        raise LoaderError(f"Failed to load raw data into database: {exc}") from exc
    finally:
        conn.close()


def get_raw_record(
    record_id: int,
    db_path: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """Retrieve a single raw_data record by primary key, deserializing JSON fields.

    Args:
        record_id: Primary key id.
        db_path: Optional SQLite database file path.

    Returns:
        dict: Deserialized raw record or None if not found.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM raw_data WHERE id = ?;", (record_id,))
        row = cursor.fetchone()
        if not row:
            return None

        headings = json.loads(row["headings"]) if row["headings"] else []
        links = json.loads(row["links"]) if row["links"] else []

        return {
            "id": row["id"],
            "source_url": row["source_url"],
            "page_title": row["page_title"] or "",
            "headings": headings,
            "links": links,
            "content": row["content"] or "",
            "content_hash": row["content_hash"] or "",
            "extracted_at": row["extracted_at"],
        }
    finally:
        conn.close()
