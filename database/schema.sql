-- Initial database schema for Website-to-Database ELT Pipeline (Phase 1)

-- 1. Raw Data Table: Stores extracted content before transformation
CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    page_title TEXT,
    content TEXT,
    extracted_at TEXT NOT NULL
);

-- 2. Transformed Data Table: Stores cleaned and structured records
CREATE TABLE IF NOT EXISTS transformed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    page_title TEXT,
    content TEXT,
    transformed_at TEXT NOT NULL
);

-- 3. Pipeline Runs Table: Tracks pipeline execution history and status
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    records_extracted INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

-- Basic indexes for query performance on source_url
CREATE INDEX IF NOT EXISTS idx_raw_data_source_url ON raw_data (source_url);
CREATE INDEX IF NOT EXISTS idx_transformed_data_source_url ON transformed_data (source_url);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source_url ON pipeline_runs (source_url);
