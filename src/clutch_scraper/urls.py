"""Build clutch.co URLs: directory listings, company profiles and the lookup endpoints.

Directory pages paginate in an unusual way: the first page has no ``page`` parameter,
the second is ``?page=2``, the third ``?page=3`` and so on. ``?page=1`` is an alias of
``?page=2``, so :func:`directory_url` never sends it.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

BASE = "https://clutch.co"

Params = list[tuple[str, str]]


def directory_path(category: str) -> tuple[str, Params]:
    """Split a directory reference into its path and any query parameters it carries.

    Accepts a path (``seo-firms``, ``/agencies/digital-marketing``,
    ``developers/react-native``) or a full clutch.co URL copied from the browser
    (``https://clutch.co/seo-firms/new-york?hourly_rate=50-99``). ``page`` is dropped:
    paging is controlled by the scraper.
    """
    value = (category or "").strip()
    if not value:
        raise ValueError("a directory path such as 'seo-firms' or 'agencies/digital-marketing'")
    if value.lower().startswith(("clutch.co/", "www.clutch.co/")):
        value = "https://" + value
    parts = urlsplit(value if "://" in value else f"{BASE}/{value.lstrip('/')}")
    host = parts.netloc.lower()
    if host and host not in {"clutch.co", "www.clutch.co"}:
        raise ValueError(f"not a clutch.co URL: {category!r}")
    path = "/" + parts.path.strip("/")
    if path == "/":
        raise ValueError("a directory path such as 'seo-firms' or 'agencies/digital-marketing'")
    if path.startswith("/profile/"):
        raise ValueError(f"{category!r} is a company profile, not a directory listing")
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if k != "page"]
    return path, params


def directory_url(path: str, params: Iterable[tuple[str, str]] = (), page: int = 1) -> str:
    """The URL of one page of a directory listing (``page`` is 1-based)."""
    if page < 1:
        raise ValueError("page numbers start at 1")
    query = list(params)
    if page > 1:
        query.append(("page", str(page)))
    return f"{BASE}{path}" + (f"?{urlencode(query)}" if query else "")


def profile_slug(company: str) -> str:
    """The profile slug from a slug, a ``/profile/<slug>`` path or a profile URL."""
    value = (company or "").strip()
    if "/profile/" in value:
        value = value.split("/profile/", 1)[1]
    value = value.split("?", 1)[0].split("#", 1)[0].strip("/")
    if not value or "/" in value:
        raise ValueError(f"not a Clutch company: {company!r} (use a slug such as 'smartsites')")
    return value


def profile_url(slug: str, params: Iterable[tuple[str, str]] = (), page: int = 1) -> str:
    """A company profile; ``page`` and ``params`` select its review list."""
    if page < 1:
        raise ValueError("page numbers start at 1")
    query = list(params)
    if page > 1:
        query.append(("page", str(page)))
    return f"{BASE}/profile/{quote(slug)}" + (f"?{urlencode(query)}" if query else "")


def absolute(href: str | None) -> str | None:
    """``href`` as an absolute clutch.co URL."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BASE + href
    return href


def locations_url(query: str) -> str:
    """The location autocomplete that maps a place name to a Clutch location id."""
    return f"{BASE}/directory/locations?{urlencode({'q': query})}"


def facets_url(path: str, params: Iterable[tuple[str, str]] = ()) -> str:
    """The endpoint behind a directory's filter menus (every option with its count)."""
    return f"{BASE}/directory/facets?{urlencode([('path', path), *params])}"
