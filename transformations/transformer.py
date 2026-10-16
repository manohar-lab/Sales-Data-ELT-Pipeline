"""SQL Transformation Engine for the Website-to-Database ELT Pipeline (Phase 4).

Reads raw records from raw_data, cleans, normalizes, and validates them,
and populates transformed_data using parameterized SQL transactions and deterministic deduplication.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Optional, Union
import urllib.parse

from config import settings
from database.connection import get_connection

logger = logging.getLogger("elt_pipeline")


# =====================================================================
# Custom Exceptions
# =====================================================================

class TransformationError(Exception):
    """Raised when an error occurs during SQL transformation processing."""

    def __init__(self, message: str, summary: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.summary = summary or {}


# =====================================================================
# Validation & Text Cleaning Helpers
# =====================================================================

def is_valid_source_url(url: Optional[str]) -> bool:
    """Validate source URL syntax without triggering external HTTP or DNS requests.

    Requirements:
    - Non-empty string.
    - Only HTTP and HTTPS schemes.
    - Valid hostname present.
    - No embedded credentials (username/password).

    Args:
        url: URL string to check.

    Returns:
        bool: True if URL is syntactically valid and secure, False otherwise.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return False

    trimmed = url.strip()
    try:
        parsed = urllib.parse.urlsplit(trimmed)
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False

    if not parsed.hostname:
        return False

    if parsed.username or parsed.password or "@" in parsed.netloc:
        return False

    return True


def normalize_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize whitespace while preserving punctuation and capitalization.

    Converts empty or whitespace-only strings to None (stored as SQL NULL).

    Args:
        text: Input string.

    Returns:
        Optional[str]: Cleaned normalized string or None if empty.
    """
    if text is None or not isinstance(text, str):
        return None

    stripped = text.strip()
    if not stripped:
        return None

    # Collapse repeated internal whitespace (spaces, tabs, newlines)
    return " ".join(stripped.split())


def clean_json_headings(headings_raw: Optional[Union[str, list]]) -> tuple[Optional[str], list[str]]:
    """Clean, normalize, and validate serialized headings JSON.

    Handles malformed JSON safely without crashing the transformation run.

    Args:
        headings_raw: Raw JSON string or list of headings.

    Returns:
        tuple[Optional[str], list[str]]: (JSON string or None, list of cleaned strings)
    """
    if not headings_raw:
        return None, []

    raw_items = []
    if isinstance(headings_raw, list):
        raw_items = headings_raw
    elif isinstance(headings_raw, str):
        trimmed = headings_raw.strip()
        if not trimmed:
            return None, []
        try:
            parsed = json.loads(trimmed)
            raw_items = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Malformed headings JSON encountered; skipping optional headings field: {exc}")
            return None, []

    cleaned: list[str] = []
    for item in raw_items:
        normalized = normalize_text(str(item)) if item is not None else None
        if normalized:
            cleaned.append(normalized)

    if not cleaned:
        return None, []

    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True), cleaned


def clean_json_links(links_raw: Optional[Union[str, list]]) -> tuple[Optional[str], list[dict[str, str]]]:
    """Clean, normalize, and validate serialized links JSON.

    Handles malformed JSON safely without crashing the transformation run.

    Args:
        links_raw: Raw JSON string or list of link dictionaries.

    Returns:
        tuple[Optional[str], list[dict[str, str]]]: (JSON string or None, list of cleaned dicts)
    """
    if not links_raw:
        return None, []

    raw_items = []
    if isinstance(links_raw, list):
        raw_items = links_raw
    elif isinstance(links_raw, str):
        trimmed = links_raw.strip()
        if not trimmed:
            return None, []
        try:
            parsed = json.loads(trimmed)
            raw_items = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Malformed links JSON encountered; skipping optional links field: {exc}")
            return None, []

    cleaned: list[dict[str, str]] = []
    for item in raw_items:
        if isinstance(item, dict):
            url = item.get("url")
            if url and isinstance(url, str) and is_valid_source_url(url):
                text = normalize_text(item.get("text")) or ""
                cleaned.append({"text": text, "url": url.strip()})

    if not cleaned:
        return None, []

    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True), cleaned


def compute_transformed_hash(
    source_url: str,
    page_title: Optional[str],
    headings_json: Optional[str],
    links_json: Optional[str],
    content: str,
) -> str:
    """Generate a deterministic SHA-256 fingerprint for cleaned transformed content."""
    hasher = hashlib.sha256()
    hasher.update(source_url.strip().encode("utf-8"))
    hasher.update(b"|")
    hasher.update((page_title or "").encode("utf-8"))
    hasher.update(b"|")
    hasher.update((headings_json or "").encode("utf-8"))
    hasher.update(b"|")
    hasher.update((links_json or "").encode("utf-8"))
    hasher.update(b"|")
    hasher.update(content.encode("utf-8"))
    return hasher.hexdigest()


# =====================================================================
# Main Transformation Engine
# =====================================================================

def transform_raw_data(db_path: Optional[Path | str] = None) -> dict[str, Any]:
    """Read unprocessed records from raw_data, clean and normalize them, and write to transformed_data.

    Follows ELT pattern (Extract -> Load -> Transform).
    Raw records remain completely untouched.
    Guarantees idempotency: running repeatedly on unchanged data does not create duplicate entries.
    Executes within an atomic transaction with automatic rollback on error.

    Args:
        db_path: Optional path to the SQLite database. Defaults to settings.DATABASE_PATH.

    Returns:
        dict: Transformation run summary metrics.

    Raises:
        TransformationError: If a database error or transaction failure occurs.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    logger.info(f"Starting transformation run on database: {target_db}")

    summary: dict[str, Any] = {
        "status": "SUCCESS",
        "raw_records_read": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "records_cleaned": 0,
        "duplicates_skipped": 0,
        "records_inserted": 0,
        "records_updated": 0,
        "records_skipped": 0,
        "error_message": None,
    }

    conn = get_connection(target_db)

    try:
        with conn:
            cursor = conn.cursor()

            # 1. Query raw records ordered deterministically by id
            cursor.execute(
                """
                SELECT
                    id,
                    source_url,
                    page_title,
                    headings,
                    links,
                    content,
                    extracted_at
                FROM raw_data
                ORDER BY id ASC;
                """
            )
            raw_records = cursor.fetchall()
            summary["raw_records_read"] = len(raw_records)

            for row in raw_records:
                raw_id = row["id"]
                raw_url = row["source_url"]

                # A. URL validation (must be valid HTTP/HTTPS without credentials)
                if not is_valid_source_url(raw_url):
                    logger.warning(f"Raw record #{raw_id} rejected due to invalid source URL: {raw_url}")
                    summary["invalid_records"] += 1
                    summary["records_skipped"] += 1
                    continue

                # B. Clean text fields
                cleaned_title = normalize_text(row["page_title"])
                cleaned_content = normalize_text(row["content"])

                # C. Clean optional structured JSON
                headings_json, clean_headings = clean_json_headings(row["headings"])
                links_json, clean_links = clean_json_links(row["links"])

                # D. Missing content validation:
                # If content is missing, check if headings provide useful content; otherwise reject.
                usable_content = cleaned_content
                if not usable_content and clean_headings:
                    usable_content = " ".join(clean_headings)

                if not usable_content:
                    logger.warning(
                        f"Raw record #{raw_id} rejected: no meaningful readable content or headings found."
                    )
                    summary["invalid_records"] += 1
                    summary["records_skipped"] += 1
                    continue

                summary["records_cleaned"] += 1

                # E. Deterministic content fingerprint
                content_hash = compute_transformed_hash(
                    source_url=raw_url,
                    page_title=cleaned_title,
                    headings_json=headings_json,
                    links_json=links_json,
                    content=usable_content,
                )

                # F. Deduplication check: check if already exists in transformed_data
                cursor.execute(
                    """
                    SELECT id FROM transformed_data
                    WHERE source_url = ? AND content_hash = ?
                    LIMIT 1;
                    """,
                    (raw_url, content_hash),
                )
                existing_transformed = cursor.fetchone()

                if existing_transformed:
                    summary["duplicates_skipped"] += 1
                    summary["records_skipped"] += 1
                    continue

                # G. Insert into transformed_data using parameterized SQL
                now_utc = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    """
                    INSERT INTO transformed_data (
                        raw_id,
                        source_url,
                        page_title,
                        headings,
                        links,
                        content,
                        content_hash,
                        transformed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        raw_id,
                        raw_url,
                        cleaned_title,
                        headings_json,
                        links_json,
                        usable_content,
                        content_hash,
                        now_utc,
                    ),
                )
                summary["records_inserted"] += 1
                summary["valid_records"] += 1

        logger.info(
            f"Transformation completed: {summary['records_inserted']} inserted, "
            f"{summary['duplicates_skipped']} duplicates skipped, "
            f"{summary['invalid_records']} invalid records skipped."
        )
        return summary

    except sqlite3.Error as exc:
        err_msg = f"Database transaction failed during transformation: {exc}"
        logger.error(err_msg, exc_info=True)
        summary["status"] = "FAILED"
        summary["error_message"] = err_msg
        raise TransformationError(err_msg, summary=summary) from exc

    finally:
        conn.close()


def get_transformed_records(
    db_path: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Retrieve all records from transformed_data for inspection and testing.

    Args:
        db_path: Optional path to the database.

    Returns:
        list[dict]: List of transformed record dictionaries.
    """
    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transformed_data ORDER BY id ASC;")
        rows = cursor.fetchall()
        results = []
        for row in rows:
            headings = json.loads(row["headings"]) if row["headings"] else []
            links = json.loads(row["links"]) if row["links"] else []
            results.append({
                "id": row["id"],
                "raw_id": row["raw_id"],
                "source_url": row["source_url"],
                "page_title": row["page_title"],
                "headings": headings,
                "links": links,
                "content": row["content"],
                "content_hash": row["content_hash"],
                "transformed_at": row["transformed_at"],
            })
        return results
    finally:
        conn.close()
