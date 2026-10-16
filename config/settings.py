"""Application configuration settings for Website-to-Database ELT Pipeline.

Centralizes project directories, database paths, and runtime logging setup
using standard library pathlib without storing credentials or hardcoded machine paths.
"""

import sys
from pathlib import Path
import logging

# Base project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Runtime directories
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Database file configuration
DATABASE_PATH = DATA_DIR / "pipeline.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# Log file configuration
LOG_FILE_PATH = LOGS_DIR / "pipeline.log"

# Scraper & HTTP Configuration
REQUEST_TIMEOUT = 10  # Seconds
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes
MAX_REDIRECTS = 5
USER_AGENT = "WebsiteELTPipelineBot/1.0 (+https://github.com/manohar-lab/Website-to-Database-ELT-Pipeline)"
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


def init_directories() -> None:
    """Safely create required runtime directories if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Configure basic console and file logging.
    
    Log records are streamed to standard output and persisted to logs/pipeline.log.
    
    Args:
        log_level: The logging severity threshold (default: logging.INFO).
        
    Returns:
        logging.Logger: The configured application logger instance.
    """
    init_directories()

    logger = logging.getLogger("elt_pipeline")
    logger.setLevel(log_level)

    # Prevent attaching duplicate handlers on repeated invocations
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
