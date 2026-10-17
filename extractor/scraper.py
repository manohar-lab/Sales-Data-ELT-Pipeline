"""Website extraction engine for the Website-to-Database ELT Pipeline.

Fetches webpage content using Requests and parses structured data using Beautiful Soup.
Implements robust URL validation with SSRF protections, redirect revalidation,
streaming download limits, and structured field extraction.
"""

from datetime import datetime, timezone
import ipaddress
import logging
from pathlib import Path
import socket
from typing import Any, Optional, Union
import urllib.parse

from bs4 import BeautifulSoup
import requests

from config import settings

logger = logging.getLogger("elt_pipeline")


def sanitize_url_for_logging(url: str) -> str:
    """Return URL without sensitive credentials or query parameters for safe logging.

    Args:
        url: The raw URL string.

    Returns:
        str: Sanitized URL string safe for log outputs.
    """
    if not isinstance(url, str):
        return "<invalid-url>"
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        query_indicator = "?..." if parsed.query else ""
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}{query_indicator}"
    except Exception:
        return "<invalid-url>"


# =====================================================================
# Custom Exception Hierarchy
# =====================================================================

class ExtractionError(Exception):
    """Base exception for all extraction engine errors."""
    pass


class URLValidationError(ExtractionError):
    """Raised when URL syntax or safety validation fails (e.g., SSRF defense)."""
    pass


class RequestError(ExtractionError):
    """Raised when an HTTP request fails (network, timeout, status, size, redirect)."""
    pass


class ParsingError(ExtractionError):
    """Raised when HTML parsing fails unexpectedly."""
    pass


# =====================================================================
# URL Validation & SSRF Prevention
# =====================================================================

def is_restricted_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Check if an IP address is private, loopback, link-local, reserved, or non-global.

    Args:
        ip: IPv4Address or IPv6Address object.

    Returns:
        bool: True if the IP must be blocked to prevent SSRF, False otherwise.
    """
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


def validate_url(url: str) -> str:
    """Validate a target URL for syntactic correctness and SSRF safety.

    Requirements enforced:
    - Non-empty string.
    - Only HTTP and HTTPS schemes.
    - Valid hostname required.
    - Embedded credentials rejected.
    - Localhost and loopback destinations rejected.
    - Private, link-local, and reserved IP ranges rejected (including DNS resolution).

    Args:
        url: The target website URL.

    Returns:
        str: The normalized, validated URL.

    Raises:
        URLValidationError: If any safety or syntax rule is violated.
    """
    if not isinstance(url, str) or not url.strip():
        raise URLValidationError("URL cannot be empty.")

    trimmed_url = url.strip()

    try:
        parsed = urllib.parse.urlsplit(trimmed_url)
    except Exception as e:
        raise URLValidationError(f"Malformed URL: {e}") from e

    # Scheme verification
    if parsed.scheme.lower() not in ("http", "https"):
        raise URLValidationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
        )

    # Hostname verification
    if not parsed.hostname:
        raise URLValidationError("URL must include a valid hostname.")

    # Reject embedded userinfo (credentials)
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise URLValidationError("URLs with embedded credentials are not permitted.")

    hostname = parsed.hostname.lower()

    # Reject localhost identifiers directly
    if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".localhost"):
        raise URLValidationError(f"Access to localhost destinations is prohibited: '{parsed.hostname}'.")

    # Check IP literal or resolve hostname via DNS
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if is_restricted_ip(ip_obj):
            raise URLValidationError(
                f"Access to non-public or private IP address is prohibited: '{ip_obj}'."
            )
    except ValueError:
        # Hostname is a domain name; resolve IP addresses via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror as e:
            raise URLValidationError(f"Could not resolve hostname '{parsed.hostname}': {e}") from e

        resolved_ips = []
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            try:
                resolved_ips.append(ipaddress.ip_address(ip_str))
            except ValueError:
                continue

        if not resolved_ips:
            raise URLValidationError(f"No IP addresses resolved for hostname '{parsed.hostname}'.")

        for resolved_ip in resolved_ips:
            if is_restricted_ip(resolved_ip):
                raise URLValidationError(
                    f"Access to non-public destination is prohibited: '{parsed.hostname}' resolved to '{resolved_ip}'."
                )

    return trimmed_url


# =====================================================================
# HTTP Fetching with Streaming Size Limit & Redirect Revalidation
# =====================================================================

def fetch_html(url: str, session: Optional[requests.Session] = None) -> str:
    """Fetch HTML content from a validated public webpage.

    Enforces URL validation before every request and revalidates all redirect hops.
    Streams the response to enforce the configured byte-size limit during download.

    Args:
        url: The webpage URL to fetch.
        session: Optional requests.Session instance for connection reuse or testing.

    Returns:
        str: Decoded HTML content.

    Raises:
        URLValidationError: If URL or any redirect destination fails validation.
        RequestError: If the request fails, times out, returns HTTP errors,
                      or exceeds configured size/redirect thresholds.
    """
    current_url = validate_url(url)
    redirect_count = 0

    http = session or requests.Session()
    owns_session = session is None

    headers = {"User-Agent": settings.USER_AGENT}

    try:
        while True:
            safe_current_url = sanitize_url_for_logging(current_url)
            logger.info(f"Fetching URL: {safe_current_url}")
            try:
                response = http.get(
                    current_url,
                    headers=headers,
                    timeout=settings.REQUEST_TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                    verify=True,
                )
            except requests.Timeout as e:
                logger.error(f"Request timed out for {safe_current_url}: {e}")
                raise RequestError(f"Request timed out after {settings.REQUEST_TIMEOUT}s: {e}") from e
            except requests.ConnectionError as e:
                logger.error(f"Connection error for {safe_current_url}: {e}")
                raise RequestError(f"Connection error while fetching {safe_current_url}: {e}") from e
            except requests.RequestException as e:
                logger.error(f"HTTP request failed for {safe_current_url}: {e}")
                raise RequestError(f"HTTP request failed for {safe_current_url}: {e}") from e

            # Handle redirects manually to revalidate destination IP and scheme
            if response.status_code in (301, 302, 303, 307, 308):
                response.close()
                redirect_count += 1
                if redirect_count > settings.MAX_REDIRECTS:
                    raise RequestError(
                        f"Exceeded maximum allowed redirects ({settings.MAX_REDIRECTS})."
                    )

                location = response.headers.get("Location")
                if not location:
                    raise RequestError(
                        f"Redirect status {response.status_code} received without Location header."
                    )

                next_url = urllib.parse.urljoin(current_url, location)
                safe_next_url = sanitize_url_for_logging(next_url)
                logger.info(f"Redirecting ({redirect_count}/{settings.MAX_REDIRECTS}) to: {safe_next_url}")
                # Revalidate next destination against SSRF rules
                current_url = validate_url(next_url)
                continue

            # Non-redirect response: inspect and read content safely
            try:
                if response.status_code >= 400:
                    raise RequestError(
                        f"HTTP error response: {response.status_code} {response.reason}"
                    )

                content_type = response.headers.get("Content-Type", "")
                media_type = content_type.split(";")[0].strip().lower()
                if not media_type or media_type not in settings.ALLOWED_CONTENT_TYPES:
                    raise RequestError(
                        f"Unsupported content type '{content_type}'. Expected HTML ({', '.join(settings.ALLOWED_CONTENT_TYPES)})."
                    )

                # Check Content-Length if present
                content_length = response.headers.get("Content-Length")
                if content_length and content_length.isdigit():
                    if int(content_length) > settings.MAX_RESPONSE_SIZE:
                        raise RequestError(
                            f"Response Content-Length ({content_length} bytes) exceeds limit of {settings.MAX_RESPONSE_SIZE} bytes."
                        )

                # Enforce size limit while streaming download chunks
                downloaded_bytes = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_bytes.extend(chunk)
                        if len(downloaded_bytes) > settings.MAX_RESPONSE_SIZE:
                            raise RequestError(
                                f"Response exceeded maximum allowed size of {settings.MAX_RESPONSE_SIZE} bytes."
                            )

                encoding = response.encoding or "utf-8"
                return downloaded_bytes.decode(encoding, errors="replace")
            finally:
                response.close()

    finally:
        if owns_session:
            http.close()


# =====================================================================
# HTML Parsing & Structured Data Extraction
# =====================================================================

def extract_page_data(url: str, html_content: Optional[str] = None) -> dict[str, Any]:
    """Fetch and parse webpage HTML to extract structured content.

    Args:
        url: The webpage URL.
        html_content: Optional HTML string. If not provided, fetch_html(url) is called.

    Returns:
        dict: Predictable structured data containing:
            - source_url (str)
            - page_title (str)
            - headings (list[str])
            - links (list[dict[str, str]]) with 'text' and 'url'
            - content (str)
            - extracted_at (str, ISO 8601 UTC)

    Raises:
        URLValidationError: If URL fails validation.
        RequestError: If fetching the webpage fails.
        ParsingError: If parsing fails unexpectedly.
    """
    if html_content is None:
        html = fetch_html(url)
    else:
        # Validate URL even when HTML is provided directly
        validate_url(url)
        html = html_content

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        safe_url = sanitize_url_for_logging(url)
        logger.error(f"HTML parsing failed for {safe_url}: {e}")
        raise ParsingError(f"Failed to parse HTML from {safe_url}: {e}") from e

    # 1. Page Title
    page_title = ""
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()
    elif soup.title:
        page_title = soup.title.get_text(strip=True)

    # 2. Headings (h1 through h6)
    headings = []
    for h_tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        h_text = h_tag.get_text(separator=" ", strip=True)
        clean_heading = " ".join(h_text.split())
        if clean_heading:
            headings.append(clean_heading)

    # 3. Hyperlinks with visible text and resolved URLs
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        link_text = " ".join(a_tag.get_text(separator=" ", strip=True).split())
        resolved_url = urllib.parse.urljoin(url, href)
        links.append({
            "text": link_text,
            "url": resolved_url,
        })

    # 4. Clean readable body text
    body_target = soup.body if soup.body else soup
    # Remove scripts, styles, and non-content elements
    for unwanted in body_target.find_all(["script", "style", "noscript", "svg", "template", "iframe"]):
        unwanted.decompose()

    raw_text = body_target.get_text(separator=" ", strip=True)
    content = " ".join(raw_text.split())

    # 5. Extraction timestamp in ISO 8601 UTC
    extracted_at = datetime.now(timezone.utc).isoformat()

    return {
        "source_url": url,
        "page_title": page_title,
        "headings": headings,
        "links": links,
        "content": content,
        "extracted_at": extracted_at,
    }
