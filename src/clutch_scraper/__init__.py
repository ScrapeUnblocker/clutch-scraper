"""Scrape Clutch.co company directories, profiles and client reviews through the
ScrapeUnblocker API.

>>> from clutch_scraper import Clutch, DirectoryFilters, ReviewFilters
>>> clutch = Clutch()  # reads SCRAPEUNBLOCKER_KEY
>>> nyc = clutch.resolve_location("New York City")
>>> result = clutch.search(
...     "seo-firms",
...     DirectoryFilters(location_id=nyc.location_id, sort="rating", min_reviews=10),
...     pages=2,
... )
>>> [(c.name, c.rating, c.review_count, c.hourly_rate) for c in result.companies[:5]]
>>> profile = clutch.profile("smartsites")
>>> profile.founded, profile.service_lines[:3], profile.offices[0].city
>>> reviews = clutch.reviews("smartsites", ReviewFilters(sort="newest"), pages=3)

See https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos
"""

from __future__ import annotations

__version__ = "0.1.0"

from .errors import ClutchError, FilterError, NotFoundError, ParseError
from .models import (
    QA,
    Company,
    DirectoryPage,
    FilterChoice,
    FilterOptions,
    Location,
    Office,
    Package,
    Profile,
    Review,
    ReviewsPage,
    SearchResults,
    ServiceShare,
)
from .options import (
    BUDGETS,
    CLIENT_TYPES,
    COMPANY_SIZES,
    HOURLY_RATES,
    MIN_REVIEWS,
    PROJECT_COSTS,
    REVIEW_SORTS,
    SORTS,
    DirectoryFilters,
    ReviewFilters,
)
from .parsing import parse_directory, parse_facets, parse_locations, parse_profile, parse_reviews
from .scraper import Clutch, ignored_filters

__all__ = [
    "BUDGETS",
    "CLIENT_TYPES",
    "COMPANY_SIZES",
    "Clutch",
    "ClutchError",
    "Company",
    "DirectoryFilters",
    "DirectoryPage",
    "FilterChoice",
    "FilterError",
    "FilterOptions",
    "HOURLY_RATES",
    "Location",
    "MIN_REVIEWS",
    "NotFoundError",
    "Office",
    "PROJECT_COSTS",
    "Package",
    "ParseError",
    "Profile",
    "QA",
    "REVIEW_SORTS",
    "Review",
    "ReviewFilters",
    "ReviewsPage",
    "SORTS",
    "SearchResults",
    "ServiceShare",
    "__version__",
    "ignored_filters",
    "parse_directory",
    "parse_facets",
    "parse_locations",
    "parse_profile",
    "parse_reviews",
]
