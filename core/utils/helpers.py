import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def content_hash(title: str, source: str) -> str:
    key = f"{title.strip().lower()}|{source.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        clean_query = "&".join(
            part for part in (parsed.query or "").split("&")
            if not re.match(r"^(utm_|fbclid|gclid|ref=|source=)", part, re.I)
        )
        return parsed._replace(query=clean_query, fragment="").geturl()
    except Exception:
        return url


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def safe_get(d: dict, *keys: str, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def truncate(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""
