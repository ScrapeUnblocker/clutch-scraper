"""Scrape clutch.co through the ScrapeUnblocker ``getPageSource`` API.

:class:`Clutch` fetches Clutch's server-rendered pages and parses them:

* :meth:`Clutch.search` - a directory listing (``seo-firms``, ``web-developers``,
  ``agencies/digital-marketing``, ...) with filters, across pages, de-duplicated;
* :meth:`Clutch.profile` - a company profile with offices, service mix, pricing,
  verification and the first page of reviews;
* :meth:`Clutch.reviews` - a company's client reviews, sorted and filtered, across pages;
* :meth:`Clutch.find_locations` and :meth:`Clutch.filter_options` - the lookups behind
  the location box and the filter menus.

Throttled, blocked and timed-out requests are retried with doubling backoff. A page
without the expected data is fetched once more before :class:`ParseError` is raised.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

from .errors import NotFoundError, ParseError
from .models import (
    Company,
    DirectoryPage,
    FilterOptions,
    Location,
    Profile,
    Review,
    ReviewsPage,
    SearchResults,
)
from .options import DirectoryFilters, ReviewFilters
from .parsing import parse_directory, parse_facets, parse_locations, parse_profile, parse_reviews
from .urls import (
    directory_path,
    directory_url,
    facets_url,
    locations_url,
    profile_slug,
    profile_url,
)

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "ConnectionError",
)
_NOT_FOUND_NAMES = ("TargetNotFoundError",)

log = logging.getLogger(__name__)


def _is_named(error: BaseException, *names: str) -> bool:
    return any(cls.__name__ in names for cls in type(error).__mro__)


class _BadPage(Exception):
    """A response without the expected data (fetched once more)."""


def ignored_filters(requested: list[tuple[str, str]], page: DirectoryPage) -> list[tuple[str, str]]:
    """The requested ``(name, value)`` filters Clutch did not apply on ``page``.

    Clutch silently drops values it does not know; the page echoes the ones it used.
    """
    applied_sort = dict(parse_qsl(urlsplit(page.clutch_url or "").query)).get("sort_by")
    missing = []
    for name, value in requested:
        if name == "page":
            continue
        if name == "sort_by":
            if page.clutch_url and applied_sort != value:
                missing.append((name, value))
        elif value not in page.applied_filters.get(name, []):
            missing.append((name, value))
    return missing


class Clutch:
    """Read clutch.co directories, company profiles and reviews.

    Args:
        api_key: Your ScrapeUnblocker API key. Defaults to the
            ``SCRAPEUNBLOCKER_KEY`` environment variable (read by the SDK).
        client: A ready ``scrapeunblocker.Client`` (or anything with a compatible
            ``get_page_source``); handy for tests.
        proxy_country: Country to route requests through. Clutch serves the same
            listings everywhere; ``"us"`` (the default) gives US-formatted pages.
        max_retries: Extra attempts for a request that fails transiently.
        backoff: Seconds before the first retry; doubles on each retry.
        timeout: Seconds to wait for one API response.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any = None,
        proxy_country: str | None = "us",
        max_retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 180.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if client is None:
            from scrapeunblocker import Client

            client = Client(api_key=api_key, timeout=timeout)
        self.client = client
        self.proxy_country = proxy_country or None
        self.max_retries = max_retries
        self.backoff = backoff
        self.sleep = sleep
        #: Number of API requests made so far.
        self.requests = 0

    # -- fetching ----------------------------------------------------------------------

    def fetch(self, url: str, parse: Callable[[str], Any]) -> Any:
        """Fetch ``url`` and return ``parse(body)``, retrying transient failures.

        A 404 from Clutch raises :class:`NotFoundError`. If ``parse`` raises
        :class:`ParseError` the page is fetched once more before the error is raised.
        """
        kwargs: dict[str, Any] = {}
        if self.proxy_country:
            kwargs["proxy_country"] = self.proxy_country
        attempt = 0
        bad_pages = 0
        while True:
            self.requests += 1
            try:
                try:
                    body = self.client.get_page_source(url, **kwargs)
                except Exception as exc:
                    if _is_named(exc, *_NOT_FOUND_NAMES):
                        raise NotFoundError(f"Clutch answered 404 for {url}") from exc
                    raise
                try:
                    return parse(body if isinstance(body, str) else str(body))
                except ParseError as exc:
                    bad_pages += 1
                    if bad_pages > 1:
                        raise
                    raise _BadPage(str(exc)) from None
            except Exception as exc:
                retryable = isinstance(exc, _BadPage) or _is_named(exc, *_TRANSIENT_NAMES)
                if not retryable or attempt >= self.max_retries:
                    if isinstance(exc, _BadPage):
                        raise ParseError(f"{exc} ({url})") from None
                    raise
                reason = str(exc) if isinstance(exc, _BadPage) else type(exc).__name__
                log.info("retrying %s after %s", url, reason)
                self.sleep(self.backoff * (2**attempt))
                attempt += 1

    # -- directories -------------------------------------------------------------------

    def directory_page(
        self,
        directory: str,
        filters: DirectoryFilters | None = None,
        page: int = 1,
    ) -> DirectoryPage:
        """One page of a directory listing.

        Args:
            directory: A directory path (``seo-firms``, ``web-developers``,
                ``agencies/digital-marketing``, ``it-services/msp``) or a clutch.co
                listing URL copied from the browser, filters included.
            filters: Extra filters (location, rates, sizes, sort, ...).
            page: 1-based page number (Clutch shows up to 50 companies per page).
        """
        path, params = directory_path(directory)
        params += (filters or DirectoryFilters()).to_params()
        url = directory_url(path, params, page)
        return self.fetch(url, lambda html: parse_directory(html, url=url, page=page))

    def iter_directory(
        self,
        directory: str,
        filters: DirectoryFilters | None = None,
        *,
        pages: int = 1,
        start_page: int = 1,
    ) -> Iterator[DirectoryPage]:
        """Directory pages from ``start_page`` on, stopping after ``pages`` pages or at
        the last page."""
        for page in range(start_page, start_page + max(pages, 0)):
            result = self.directory_page(directory, filters, page)
            yield result
            if not result.companies or not result.has_next:
                return

    def search(
        self,
        directory: str,
        filters: DirectoryFilters | None = None,
        *,
        pages: int = 1,
        start_page: int = 1,
        limit: int | None = None,
        organic_only: bool = False,
        min_rating: float | None = None,
    ) -> SearchResults:
        """Companies from a directory listing, across pages.

        Companies are de-duplicated by Clutch id (sponsored placements can repeat a
        company that also ranks organically) and numbered in the order collected.

        Args:
            directory: Directory path or clutch.co listing URL (see :meth:`directory_page`).
            filters: Location, hourly rate, budget, size, industry, sort, ...
            pages: How many pages to read (50 companies each, fewer for some locations).
            start_page: First page to read.
            limit: Stop after this many companies.
            organic_only: Skip paid placements (``Sponsor`` / ``Nearby Sponsor``).
            min_rating: Keep only companies rated at least this (unrated ones are dropped).
        """
        path, own_params = directory_path(directory)
        requested = own_params + (filters or DirectoryFilters()).to_params()
        companies: list[Company] = []
        seen: set[str] = set()
        result: SearchResults | None = None
        for page in self.iter_directory(directory, filters, pages=pages, start_page=start_page):
            if result is None:
                result = SearchResults(
                    url=page.url,
                    total=page.total,
                    companies=companies,
                    pages_fetched=0,
                    applied_filters=page.applied_filters,
                    applied_labels=page.applied_labels,
                    ignored_filters=ignored_filters(requested, page) if page.companies else [],
                    heading=page.heading,
                )
            result.pages_fetched += 1
            for company in page.companies:
                key = company.company_id or company.slug
                if key in seen:
                    continue
                seen.add(key)
                if organic_only and company.sponsored:
                    continue
                if min_rating is not None and (company.rating or 0) < min_rating:
                    continue
                company.rank = len(companies) + 1
                companies.append(company)
                if limit is not None and len(companies) >= limit:
                    return result
        if result is None:
            url = directory_url(path, requested, start_page)
            return SearchResults(url=url, total=0, companies=[], pages_fetched=0)
        return result

    def filter_options(
        self, directory: str, filters: DirectoryFilters | None = None
    ) -> list[FilterOptions]:
        """Every filter menu of a directory with its values and company counts
        (industries, services, focus areas, budgets, ...). Counts reflect ``filters``.

        This endpoint returns a large response and can take 20 s or more.
        """
        path, params = directory_path(directory)
        params += (filters or DirectoryFilters()).to_params()
        options = self.fetch(facets_url(path, params), parse_facets)
        if not options:
            raise NotFoundError(f"no filters for {path} (is it a Clutch directory?)")
        return options

    def find_locations(self, query: str) -> list[Location]:
        """Places matching ``query`` with their Clutch location ids."""
        if not query.strip():
            raise ValueError("a place name such as 'London' or 'New York City'")
        return self.fetch(locations_url(query.strip()), parse_locations)

    def resolve_location(self, query: str) -> Location:
        """The best match for a place name (Clutch's first suggestion that has companies)."""
        matches = self.find_locations(query)
        for location in matches:
            if location.has_companies:
                return location
        if matches:
            return matches[0]
        raise NotFoundError(f"Clutch knows no location matching {query!r}")

    # -- companies ---------------------------------------------------------------------

    def profile(self, company: str) -> Profile:
        """A company profile, by slug (``smartsites``) or profile URL."""
        slug = profile_slug(company)
        url = profile_url(slug)
        return self.fetch(url, lambda html: parse_profile(html, url=url))

    def reviews_page(
        self, company: str, filters: ReviewFilters | None = None, page: int = 1
    ) -> ReviewsPage:
        """One page of a company's reviews (10 per page; page 1 adds a pinned one)."""
        slug = profile_slug(company)
        url = profile_url(slug, (filters or ReviewFilters()).to_params(), page)
        return self.fetch(url, lambda html: parse_reviews(html, url=url, page=page))

    def reviews(
        self,
        company: str,
        filters: ReviewFilters | None = None,
        *,
        pages: int = 1,
        start_page: int = 1,
        limit: int | None = None,
    ) -> list[Review]:
        """A company's client reviews across pages, de-duplicated by review id."""
        out: list[Review] = []
        seen: set[str] = set()
        for page in range(start_page, start_page + max(pages, 0)):
            result = self.reviews_page(company, filters, page)
            for review in result.reviews:
                if review.review_id in seen:
                    continue
                seen.add(review.review_id)
                out.append(review)
                if limit is not None and len(out) >= limit:
                    return out
            if not result.reviews or result.last_page is None or page >= result.last_page:
                break
        return out
