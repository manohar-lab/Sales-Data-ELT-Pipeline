"""SQLite database connection and initialization module for the ELT Pipeline.

Provides reusable database connection handling and schema initialization.
Configures sqlite3.Row as the row factory and manages directory creation.
"""

from pathlib import Path
import sqlite3
from typing import Optional
import logging

from config import settings

logger = logging.getLogger("elt_pipeline")


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Establish and return an active SQLite database connection.

    Configures sqlite3.Row as the row factory to allow column access by name.
    Ensures that the directory for the target database file exists prior to connecting.

    Args:
        db_path: Optional path to the SQLite database file.
                 Defaults to settings.DATABASE_PATH.

    Returns:
        sqlite3.Connection: Open SQLite database connection.

    Raises:
        sqlite3.Error: If the connection attempt fails.
    """
    target_path = Path(db_path) if db_path is not None else settings.DATABASE_PATH

    # Ensure parent directory exists before establishing connection
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        connection = sqlite3.connect(target_path)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to SQLite database at {target_path}: {e}")
        raise


def init_db(
    db_path: Optional[Path | str] = None,
    schema_path: Optional[Path | str] = None,
) -> None:
    """Initialize the SQLite database schema using schema.sql.

    Executes schema definitions within a context manager. Safe to execute
    repeatedly due to CREATE TABLE IF NOT EXISTS statements.

    Args:
        db_path: Optional path to the database file. Defaults to settings.DATABASE_PATH.
        schema_path: Optional path to the schema.sql file. Defaults to settings.SCHEMA_PATH.

    Raises:
        FileNotFoundError: If the schema SQL file does not exist.
        sqlite3.Error: If schema execution fails.
    """
    sql_file = Path(schema_path) if schema_path is not None else settings.SCHEMA_PATH

    if not sql_file.is_file():
        err_msg = f"Database schema file not found at: {sql_file}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    with open(sql_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    target_db = Path(db_path) if db_path is not None else settings.DATABASE_PATH
    conn = get_connection(target_db)
    try:
        with conn:
            conn.executescript(schema_sql)
        logger.info(f"Database schema initialized successfully at: {target_db}")
    except sqlite3.Error as e:
        logger.error(f"Failed to execute database schema at {target_db}: {e}")
        raise
    finally:
        conn.close()
