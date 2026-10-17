"""Unit tests for the website extraction engine (Phase 2).

Tests URL validation, SSRF protections, HTML fetching, redirect security,
streaming response-size limits, and structured field extraction.
All network operations and DNS lookups are strictly mocked.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from config import settings
from extractor.scraper import (
    ExtractionError,
    ParsingError,
    RequestError,
    URLValidationError,
    extract_page_data,
    fetch_html,
    is_restricted_ip,
    validate_url,
)
import main


# =====================================================================
# Fixtures & Helpers
# =====================================================================

SAMPLE_VALID_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page Title</title>
    <style>body { background-color: #fff; }</style>
    <script>console.log("script executed");</script>
</head>
<body>
    <h1>Main Heading</h1>
    <h2>Subheading 1</h2>
    <h3>Subheading 2</h3>
    <p>   This is readable    body text with excessive whitespace.   </p>
    <a href="/about">About Us</a>
    <a href="https://example.com/contact">Contact Us</a>
    <script>alert("another script");</script>
    <noscript>Please enable javascript</noscript>
</body>
</html>
"""


def mock_dns_public(hostname, port):
    """Mock getaddrinfo to return a safe public IP address."""
    return [(2, 1, 0, "", ("93.184.216.34", 80))]


def mock_dns_private(hostname, port):
    """Mock getaddrinfo to return a private LAN IP address."""
    return [(2, 1, 0, "", ("192.168.1.100", 80))]


# =====================================================================
# 1. URL Validation Tests (SSRF & Syntax)
# =====================================================================

def test_validate_url_valid_http():
    """Verify that a valid public HTTP URL passes validation."""
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        result = validate_url("http://example.com")
        assert result == "http://example.com"


def test_validate_url_valid_https():
    """Verify that a valid public HTTPS URL passes validation."""
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        result = validate_url("https://example.com/path?query=1")
        assert result == "https://example.com/path?query=1"


@pytest.mark.parametrize("invalid_url", [
    "",
    "   ",
    None,
    ":///malformed-url",
    "htp:/missing-slash",
])
def test_validate_url_empty_or_malformed(invalid_url):
    """Verify that empty, non-string, or malformed URLs are rejected."""
    with pytest.raises(URLValidationError):
        validate_url(invalid_url)


@pytest.mark.parametrize("unsupported_url", [
    "ftp://example.com/file.txt",
    "file:///etc/passwd",
    "ssh://example.com",
    "javascript:alert(1)",
    "data:text/html,<html></html>",
])
def test_validate_url_unsupported_scheme(unsupported_url):
    """Verify that schemes other than HTTP and HTTPS are rejected."""
    with pytest.raises(URLValidationError, match="Unsupported URL scheme"):
        validate_url(unsupported_url)


@pytest.mark.parametrize("credential_url", [
    "http://user:password@example.com",
    "https://admin@example.com",
    "http://:secret@example.com",
])
def test_validate_url_embedded_credentials(credential_url):
    """Verify that URLs with embedded usernames or passwords are rejected."""
    with pytest.raises(URLValidationError, match="embedded credentials"):
        validate_url(credential_url)


@pytest.mark.parametrize("private_url", [
    "http://localhost",
    "http://localhost:8080",
    "http://test.localhost",
    "http://127.0.0.1",
    "http://127.0.0.2",
    "http://10.0.0.1",
    "http://172.16.0.1",
    "http://192.168.1.1",
    "http://169.254.169.254",  # Cloud metadata IP
    "http://0.0.0.0",
    "http://[::1]",
])
def test_validate_url_private_or_loopback(private_url):
    """Verify that localhost, loopback, private, and link-local destinations are rejected."""
    with pytest.raises(URLValidationError):
        validate_url(private_url)


def test_validate_url_dns_resolves_to_private():
    """Verify that a public-looking domain resolving to a private IP is rejected."""
    with patch("socket.getaddrinfo", side_effect=mock_dns_private):
        with pytest.raises(URLValidationError, match="Access to non-public destination is prohibited"):
            validate_url("http://internal-spoof.com")


# =====================================================================
# 2. Structured Data Extraction Tests
# =====================================================================

def test_extract_page_data_success():
    """Verify extraction of title, headings, links, readable content, and timestamp."""
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        data = extract_page_data("https://example.com/test", html_content=SAMPLE_VALID_HTML)

    assert data["source_url"] == "https://example.com/test"
    assert data["page_title"] == "Test Page Title"
    assert data["headings"] == ["Main Heading", "Subheading 1", "Subheading 2"]

    # Verify links extraction and URL resolution
    assert len(data["links"]) == 2
    assert data["links"][0] == {"text": "About Us", "url": "https://example.com/about"}
    assert data["links"][1] == {"text": "Contact Us", "url": "https://example.com/contact"}

    # Verify scripts/styles/noscript are removed and whitespace normalized
    assert "console.log" not in data["content"]
    assert "background-color" not in data["content"]
    assert "Please enable javascript" not in data["content"]
    assert "Main Heading Subheading 1 Subheading 2 This is readable body text with excessive whitespace. About Us Contact Us" in data["content"]

    # Verify ISO 8601 UTC timestamp is recorded
    assert "T" in data["extracted_at"]


def test_extract_page_data_missing_title():
    """Verify extraction handles missing <title> tag gracefully."""
    html_without_title = "<html><body><h1>Only Heading</h1><p>Body content</p></body></html>"
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        data = extract_page_data("https://example.com", html_content=html_without_title)

    assert data["page_title"] == ""
    assert data["headings"] == ["Only Heading"]
    assert data["content"] == "Only Heading Body content"


def test_extract_page_data_empty_body():
    """Verify extraction handles an empty HTML body gracefully."""
    html_empty_body = "<html><head><title>Empty Page</title></head><body></body></html>"
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        data = extract_page_data("https://example.com", html_content=html_empty_body)

    assert data["page_title"] == "Empty Page"
    assert data["headings"] == []
    assert data["links"] == []
    assert data["content"] == ""


def test_extract_page_data_malformed_html():
    """Verify that malformed or unclosed HTML tags parse without crashing."""
    malformed_html = "<head><title>Page Title</title><body><h1>Unclosed heading<p>Unclosed paragraph<a href='/target'>Link"
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        data = extract_page_data("https://example.com", html_content=malformed_html)

    assert data["page_title"] == "Page Title"
    assert any("Unclosed heading" in h for h in data["headings"])
    assert len(data["links"]) == 1
    assert data["links"][0]["url"] == "https://example.com/target"


def test_extract_page_data_completely_broken_html():
    """Verify that completely broken HTML syntax still extracts without crashing."""
    broken_html = "<<<<>>><title>Broken<not-a-tag>text</title><<<<>>>"
    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        data = extract_page_data("https://example.com", html_content=broken_html)
    assert isinstance(data, dict)
    assert data["source_url"] == "https://example.com"


# =====================================================================
# 3. HTTP Fetching & Security Enforcement Tests
# =====================================================================

def test_fetch_html_timeout():
    """Verify that request timeouts raise RequestError."""
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.Timeout("Connection timed out")

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(RequestError, match="timed out"):
            fetch_html("https://example.com", session=mock_session)


def test_fetch_html_http_error_response():
    """Verify that HTTP 4xx or 5xx responses raise RequestError."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.reason = "Not Found"

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(RequestError, match="HTTP error response: 404"):
            fetch_html("https://example.com", session=mock_session)


def test_fetch_html_unsupported_content_type():
    """Verify that responses with non-HTML content types are rejected."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/pdf"}

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(RequestError, match="Unsupported content type"):
            fetch_html("https://example.com", session=mock_session)


def test_fetch_html_response_exceeds_size_limit():
    """Verify that responses exceeding MAX_RESPONSE_SIZE are stopped during streaming."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html"}
    # Emit chunks that total more than MAX_RESPONSE_SIZE
    chunk_size = 1024 * 1024  # 1 MB
    mock_response.iter_content.return_value = [b"A" * chunk_size] * 6  # 6 MB > 5 MB limit

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(RequestError, match="exceeded maximum allowed size"):
            fetch_html("https://example.com", session=mock_session)


def test_fetch_html_safe_redirect():
    """Verify that safe redirects are followed and content retrieved."""
    # Step 1: 301 redirect to /page2
    redirect_resp = MagicMock()
    redirect_resp.status_code = 301
    redirect_resp.headers = {"Location": "https://example.com/page2"}

    # Step 2: 200 OK HTML
    final_resp = MagicMock()
    final_resp.status_code = 200
    final_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    final_resp.iter_content.return_value = [b"<html><body><h1>Redirected Page</h1></body></html>"]
    final_resp.encoding = "utf-8"

    mock_session = MagicMock()
    mock_session.get.side_effect = [redirect_resp, final_resp]

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        content = fetch_html("https://example.com/page1", session=mock_session)
        assert "Redirected Page" in content
        assert mock_session.get.call_count == 2


def test_fetch_html_unsafe_redirect_destination():
    """Verify that redirects targeting private internal IP addresses are blocked (SSRF defense)."""
    redirect_resp = MagicMock()
    redirect_resp.status_code = 302
    redirect_resp.headers = {"Location": "http://169.254.169.254/latest/meta-data"}

    mock_session = MagicMock()
    mock_session.get.return_value = redirect_resp

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(URLValidationError, match="Access to non-public or private IP"):
            fetch_html("https://example.com/gateway", session=mock_session)


def test_fetch_html_exceeded_max_redirects():
    """Verify that endless redirect loops are stopped at MAX_REDIRECTS."""
    redirect_resp = MagicMock()
    redirect_resp.status_code = 302
    redirect_resp.headers = {"Location": "https://example.com/loop"}

    mock_session = MagicMock()
    mock_session.get.return_value = redirect_resp

    with patch("socket.getaddrinfo", side_effect=mock_dns_public):
        with pytest.raises(RequestError, match="Exceeded maximum allowed redirects"):
            fetch_html("https://example.com/start", session=mock_session)


# =====================================================================
# 4. CLI Entry Point Tests (main.py)
# =====================================================================

def test_cli_phase_2_success(capsys):
    """Verify CLI prints expected summary on successful URL extraction."""
    mock_data = {
        "source_url": "https://example.com",
        "page_title": "Sample Title",
        "headings": ["Heading 1", "Heading 2"],
        "links": [{"text": "Link 1", "url": "https://example.com/1"}],
        "content": "Sample readable text content for testing.",
        "extracted_at": "2026-10-16T12:00:00+00:00",
    }
    with patch("main.extract_page_data", return_value=mock_data):
        exit_code = main.main(["--url", "https://example.com", "--extract-only"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Phase 2: Website Extraction Engine" in captured.out
        assert "Page Title:       Sample Title" in captured.out
        assert "Headings Found:   2" in captured.out
        assert "Links Found:      1" in captured.out
        assert "Sample readable text" in captured.out


def test_cli_phase_2_failure(capsys):
    """Verify CLI reports error and exits nonzero when extraction fails."""
    with patch("main.extract_page_data", side_effect=URLValidationError("Invalid test URL")):
        exit_code = main.main(["--url", "http://invalid-url", "--extract-only"])
        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Extraction Error: Invalid test URL" in captured.err


def test_cli_phase_1_preserved():
    """Verify running CLI with no arguments invokes Phase 1 setup."""
    with patch("main.init_db") as mock_init:
        exit_code = main.main([])
        assert exit_code == 0
        mock_init.assert_called_once()
