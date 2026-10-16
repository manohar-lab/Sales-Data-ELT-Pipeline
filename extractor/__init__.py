"""Extractor package for the Website-to-Database ELT Pipeline."""

from extractor.scraper import (
    ExtractionError,
    URLValidationError,
    RequestError,
    ParsingError,
    validate_url,
    fetch_html,
    extract_page_data,
)

__all__ = [
    "ExtractionError",
    "URLValidationError",
    "RequestError",
    "ParsingError",
    "validate_url",
    "fetch_html",
    "extract_page_data",
]
