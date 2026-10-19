"""Constrain URLs sent to TinyFish and rendered as source links."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit

import tldextract

# Use the bundled Public Suffix List only; never make a hidden suffix-list request.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)


def public_url(value: str | None) -> str | None:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port not in {None, 80, 443}:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            # Block local/internal names and numeric encodings; TinyFish also rejects
            # private DNS resolution and unsafe redirects on its own infrastructure.
            domain = _extract(host)
            if not domain.suffix or host.endswith((".localhost", ".local", ".internal")):
                return None
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    except (ValueError, UnicodeError):
        return None


def registered_domain(url: str) -> str:
    parsed = _extract(urlsplit(url).hostname or "")
    return parsed.top_domain_under_public_suffix


def domain_label(url: str) -> str:
    return _extract(urlsplit(url).hostname or "").domain


def same_page(first: str | None, second: str | None) -> bool:
    if not first or not second:
        return False
    a, b = urlsplit(first), urlsplit(second)
    return (a.hostname, a.path.rstrip("/")) == (b.hostname, b.path.rstrip("/"))
