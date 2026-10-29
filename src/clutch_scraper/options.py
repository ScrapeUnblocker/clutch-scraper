"""Directory and review filters, with the values clutch.co accepts.

The value lists here are the ones every Clutch directory shares (sort orders, hourly
rate bands, review-count steps, budgets, company sizes, client types). Industries,
services and focus areas differ per directory: list them with
``clutch-scraper filters <directory>`` (:meth:`~clutch_scraper.Clutch.filter_options`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .errors import FilterError

#: ``--sort`` name -> Clutch ``sort_by`` value.
SORTS = {
    "sponsored": "Sponsorship",
    "verified": "Verification",
    "rank": "ClutchRank",
    "reviews": "NumberOfReviews",
    "rating": "ReviewRating",
    "name": "CompanyName",
}
#: Average hourly rate bands (``0-25`` is "< $25", ``300`` is "$300+").
HOURLY_RATES = ("0-25", "25-49", "50-99", "100-149", "150-199", "200-300", "300")
#: "At least N reviews" steps.
MIN_REVIEWS = (0, 1, 3, 5, 10, 15, 20)
#: Client budget: companies whose minimum project size fits under this many USD.
BUDGETS = (5000, 10000, 25000, 50000, 75000, 100000, 250000)
#: Employee-count bands: short name -> Clutch value.
COMPANY_SIZES = {
    "freelancer": "Freelancer",
    "2-9": "2 - 9",
    "10-49": "10 - 49",
    "50-249": "50 - 249",
    "250-999": "250 - 999",
    "1000-9999": "1,000 - 9,999",
    "10000+": "10,000+",
}
#: Client focus: short name -> Clutch value.
CLIENT_TYPES = {
    "small": "field_pp_cs_small_biz",
    "midmarket": "field_pp_cs_midmarket",
    "enterprise": "field_pp_cs_enterprise",
}

#: Review list orders: short name -> Clutch value.
REVIEW_SORTS = {
    "relevance": "relevance_desc",
    "newest": "date_desc",
    "rating-high": "rating_desc",
    "rating-low": "rating_asc",
}
#: Reviewed project size: short name -> Clutch value.
PROJECT_COSTS = {
    "under-10k": "less_10000",
    "10k-50k": "10000",
    "50k-200k": "50000",
    "200k-1m": "1000000",
    "1m-10m": "10000000",
    "over-10m": "more_10000000",
    "confidential": "confidential",
}

_INDUSTRY_PREFIX = "field_pp_if_"
_SERVICE_PREFIX = "field_pp_sl_"


def _choose(value: str, allowed: Iterable[str], what: str) -> str:
    allowed = list(allowed)
    if value not in allowed:
        raise FilterError(f"unknown {what} {value!r}; choose from: {', '.join(allowed)}")
    return value


def _mapped(value: str, mapping: dict[str, str], what: str) -> str:
    key = value.strip().lower().replace(" ", "")
    if key in mapping:
        return mapping[key]
    if value in mapping.values():
        return value
    raise FilterError(f"unknown {what} {value!r}; choose from: {', '.join(mapping)}")


def _prefixed(value: str, prefix: str) -> str:
    value = value.strip()
    return value if value.startswith("field_") else prefix + value


def normalize_hourly_rate(value: str) -> str:
    """``"50-99"``, ``"$50-$99"`` or ``"300+"`` -> the Clutch band value."""
    key = value.strip().replace("$", "").replace(" ", "").rstrip("+")
    if key.startswith("<"):
        key = "0-" + key[1:]
    return _choose(key, HOURLY_RATES, "hourly rate")


def normalize_sort(value: str) -> str:
    return SORTS[_choose(value.strip().lower(), SORTS, "sort")]


@dataclass
class DirectoryFilters:
    """Filters for a directory listing, mirroring the menus on clutch.co.

    Values are validated when the URL is built; :class:`~clutch_scraper.FilterError`
    lists the accepted values.
    """

    #: Clutch location id (see :meth:`~clutch_scraper.Clutch.find_locations`).
    location_id: int | None = None
    #: One of :data:`SORTS` (``rank``, ``rating``, ``reviews``, ...).
    sort: str | None = None
    #: Any of :data:`HOURLY_RATES`.
    hourly_rates: Sequence[str] = field(default_factory=list)
    #: One of :data:`MIN_REVIEWS`.
    min_reviews: int | None = None
    #: One of :data:`BUDGETS` (USD).
    budget: int | None = None
    #: Any of :data:`COMPANY_SIZES` (short names or Clutch values).
    company_sizes: Sequence[str] = field(default_factory=list)
    #: Any of :data:`CLIENT_TYPES`.
    client_types: Sequence[str] = field(default_factory=list)
    #: Industry slugs such as ``ecommerce`` or ``field_pp_if_ecommerce``.
    industries: Sequence[str] = field(default_factory=list)
    #: Extra service lines such as ``web_design`` or ``field_pp_sl_web_design``.
    services: Sequence[str] = field(default_factory=list)
    #: Focus-area slugs as listed by ``filters`` (``field_pp_seo_local_search``, ...).
    focus_areas: Sequence[str] = field(default_factory=list)
    #: Only Clutch-verified companies.
    verified: bool = False
    #: Only companies offering the Clutch Guarantee.
    clutch_guarantee: bool = False
    #: Any other ``(name, value)`` query parameter, passed through as is.
    extra: Sequence[tuple[str, str]] = field(default_factory=list)

    def to_params(self) -> list[tuple[str, str]]:
        """The query parameters for these filters (multi-value filters repeat the key)."""
        params: list[tuple[str, str]] = []
        if self.location_id is not None:
            params.append(("geona_id", str(int(self.location_id))))
        for rate in self.hourly_rates:
            params.append(("hourly_rate", normalize_hourly_rate(rate)))
        if self.min_reviews:
            reviews = _choose(str(self.min_reviews), map(str, MIN_REVIEWS), "minimum reviews")
            params.append(("reviews", reviews))
        if self.budget:
            params.append(("client_budget", _choose(str(self.budget), map(str, BUDGETS), "budget")))
        for size in self.company_sizes:
            params.append(("agency_size", _mapped(size, COMPANY_SIZES, "company size")))
        for client in self.client_types:
            params.append(("client_type", _mapped(client, CLIENT_TYPES, "client type")))
        for industry in self.industries:
            params.append(("industries", _prefixed(industry, _INDUSTRY_PREFIX)))
        for service in self.services:
            params.append(("related_services", _prefixed(service, _SERVICE_PREFIX)))
        for focus in self.focus_areas:
            params.append(("focus_areas", focus.strip()))
        if self.verified:
            params.append(("verification", "true"))
        if self.clutch_guarantee:
            params.append(("clutch_guarantee", "true"))
        if self.sort:
            params.append(("sort_by", normalize_sort(self.sort)))
        params.extend((str(k), str(v)) for k, v in self.extra)
        return params


@dataclass
class ReviewFilters:
    """Filters for a company's review list, mirroring the menus on its profile."""

    #: One of :data:`REVIEW_SORTS`.
    sort: str | None = None
    #: One of :data:`PROJECT_COSTS`.
    project_cost: str | None = None
    #: Reviewer industry, e.g. ``retail`` or ``field_pp_if_retail``.
    industry: str | None = None
    #: Services in the reviewed project, e.g. ``seo`` or ``field_pp_sl_seo``.
    services: Sequence[str] = field(default_factory=list)
    #: Clutch location id of the reviewer.
    location_id: int | None = None

    def to_params(self) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        if self.sort:
            params.append(("sort_by", _mapped(self.sort, REVIEW_SORTS, "review sort")))
        if self.project_cost:
            params.append(
                ("project_cost", _mapped(self.project_cost, PROJECT_COSTS, "project cost"))
            )
        if self.industry:
            params.append(("industry", _prefixed(self.industry, _INDUSTRY_PREFIX)))
        for service in self.services:
            params.append(("service_provided", _prefixed(service, _SERVICE_PREFIX)))
        if self.location_id is not None:
            params.append(("location", str(int(self.location_id))))
        return params
