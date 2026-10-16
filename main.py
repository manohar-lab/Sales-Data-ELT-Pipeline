"""Website-to-Database ELT Pipeline - Application Entry Point (Phase 1).

Initializes runtime directories, logging configuration, and the SQLite database schema.
Does not prompt for URLs or execute extraction, which belong to later phases.
"""

import sys
from config import settings
from database.connection import init_db


def main() -> int:
    """Run the Phase 1 startup sequence.

    1. Configure console and file logging.
    2. Initialize required runtime directories (data/, logs/).
    3. Initialize SQLite database schema and tables.
    4. Print startup information and database location.
    5. Exit cleanly.
    """
    print("=" * 65)
    print(" Website-to-Database ELT Pipeline")
    print(" Phase 1: Project Setup & Database Initialization")
    print("=" * 65)

    logger = settings.setup_logging()

    try:
        # Step 1: Ensure runtime directories exist
        settings.init_directories()
        logger.info("Runtime directories initialized.")

        # Step 2: Initialize SQLite database and tables
        init_db()
        logger.info("SQLite database and tables initialized successfully.")

        # Step 3 & 4: Display status and path
        print(f"Database File:   {settings.DATABASE_PATH.resolve()}")
        print("Database Status: Successfully initialized (tables created)")
        print(f"Logs Directory:  {settings.LOGS_DIR.resolve()}")
        print("=" * 65)
        print("Phase 1 initialization complete. System is ready for Phase 2.")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"Error during initialization: {exc}", file=sys.stderr)
        logger.error(f"Startup failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
