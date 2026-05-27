"""Best-effort full-article body fetcher.

News APIs (NewsAPI, MediaStack) typically return only short snippets. To
give the LLM extractor enough context to fill in court / judge / docket /
investigating-agency fields, we hit the source URL and pull the main
article body with BeautifulSoup heuristics.

Many sites paywall or block scrapers; in those cases we return None and
the caller falls back to whatever snippet the news API provided.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# A realistic browser UA reduces the rate of soft-block responses.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags we always strip before harvesting text.
_NOISE_TAGS = (
    "script", "style", "nav", "footer", "header", "aside",
    "iframe", "noscript", "form", "button",
)

# Cap how much text we forward to the LLM — well above what any sentencing
# article needs, and within Gemini's context comfort zone.
_MAX_CHARS = 15000


def _is_safe_public_url(url: str) -> bool:
    """SSRF guard.

    URLs in this app come from third-party search APIs (NewsAPI, MediaStack,
    GDELT, SerpAPI, Tavily). A malicious or compromised result could point at
    internal infrastructure (cloud metadata services, internal admin APIs,
    LAN hosts). We resolve every hostname and reject any address in the
    loopback, private, link-local, or multicast ranges before issuing the
    HTTP request.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def fetch_article_body(url: str, timeout: float = 15.0) -> str | None:
    """Return main article body text, or None if the URL can't be fetched
    or parsed.

    This is intentionally best-effort: paywalled or anti-bot sites will
    return None and the caller should fall back to the API-provided snippet.
    Any URL resolving to a non-public IP is refused (SSRF guard).
    """
    if not _is_safe_public_url(url):
        return None
    try:
        # follow_redirects=False so an attacker can't get the destination
        # validated and then 302 us into an internal address.
        r = httpx.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=False,
        )
        # Manually walk up to 5 redirect hops, re-validating each Location.
        hops = 0
        while r.status_code in (301, 302, 303, 307, 308) and "location" in r.headers and hops < 5:
            next_url = httpx.URL(r.headers["location"])
            if not next_url.is_absolute_url:
                next_url = r.url.join(next_url)
            if not _is_safe_public_url(str(next_url)):
                return None
            r = httpx.get(
                str(next_url),
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                follow_redirects=False,
            )
            hops += 1
    except Exception:
        return None
    if r.status_code != 200:
        return None
    content_type = (r.headers.get("content-type") or "").lower()
    if "html" not in content_type and "xml" not in content_type:
        return None

    try:
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None

    for tag in soup(list(_NOISE_TAGS)):
        tag.decompose()

    container = (
        soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("main")
        or soup.find("body")
    )
    if container is None:
        return None

    chunks: list[str] = []
    for el in container.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = el.get_text(" ", strip=True)
        if txt:
            chunks.append(txt)
    text = "\n\n".join(chunks).strip()
    if not text:
        return None
    return text[:_MAX_CHARS]
