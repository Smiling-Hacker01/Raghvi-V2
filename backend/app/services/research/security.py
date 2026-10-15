"""Security controls and SSRF protection for Web Research."""

import ipaddress
import re
import socket
from urllib.parse import urlparse

# Private and cloud-internal networks prohibited for SSRF defense
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Cloud metadata service (AWS/GCP/Azure)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Patterns for detecting common prompt injection attempts in untrusted web pages
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|unrestricted)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?above", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>", re.IGNORECASE),
]


class SecurityException(Exception):
    """Raised when an untrusted or disallowed network address or scheme is requested."""

    pass


def validate_url(url: str, resolve_dns: bool = True) -> bool:
    """Validate that a URL is safe to fetch and does not target internal services.

    Args:
        url: URL to validate
        resolve_dns: Whether to perform DNS resolution check

    Returns:
        True if URL is safe, raises SecurityException otherwise.
    """
    if not url or not isinstance(url, str):
        raise SecurityException("URL must be a non-empty string")

    parsed = urlparse(url)

    # 1. Scheme check: only http and https allowed
    if parsed.scheme.lower() not in ("http", "https"):
        raise SecurityException(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SecurityException("URL lacks a valid hostname")

    # Reject localhost directly
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal"):
        raise SecurityException("Access to loopback or metadata hostnames is prohibited")

    # 2. DNS resolution check against prohibited CIDRs
    if not resolve_dns:
        return True

    try:
        ip_addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecurityException(f"Could not resolve hostname: {hostname}") from exc

    for addr_info in ip_addresses:
        ip_str = addr_info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            for network in BLOCKED_NETWORKS:
                if ip_obj in network:
                    raise SecurityException(
                        f"SSRF violation: Hostname {hostname} resolves to private IP {ip_str}"
                    )
        except ValueError:
            continue

    return True


def sanitize_web_content(content: str, max_chars: int = 1500) -> str:
    """Sanitize and contain untrusted web content before feeding it into the AI context.

    - Truncates to maximum safe length.
    - Strips executable tags and control characters.
    - Neutralizes suspected prompt injection payloads.

    Args:
        content: Raw web content or snippet
        max_chars: Maximum characters to retain

    Returns:
        Sanitized, safe string
    """
    if not content:
        return ""

    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", content)

    # Strip dangerous injection phrases
    for pattern in INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED_PROMPT_INJECTION_PATTERN]", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Enforce length boundary
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "..."

    return cleaned
