-- SQL Transformation definitions for Website-to-Database ELT Pipeline (Phase 4)

-- 1. Insert cleaned and normalized record into transformed_data
-- Uses SQL functions (TRIM, NULLIF) for database-level cleaning and normalization
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
VALUES (
    :raw_id,
    :source_url,
    NULLIF(TRIM(:page_title), ''),
    :headings,
    :links,
    TRIM(:content),
    :content_hash,
    :transformed_at
);

-- 2. Check if a transformed record with the same fingerprint already exists
-- Used for deterministic deduplication and idempotency
SELECT id
FROM transformed_data
WHERE source_url = :source_url
  AND content_hash = :content_hash
LIMIT 1;

-- 3. Query candidate raw records ordered deterministically
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
