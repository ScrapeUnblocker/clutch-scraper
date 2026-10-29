"""Plain dataclasses for what the scraper returns. ``dataclasses.asdict`` makes JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ServiceShare:
    """One slice of a company's service mix ("50% Search Engine Optimization")."""

    name: str
    percent: int | None = None
    #: The Clutch directory for this service, when Clutch links one.
    url: str | None = None


@dataclass
class Company:
    """A company card from a directory listing."""

    #: Position in the collected results (1-based, after de-duplication).
    rank: int
    #: Directory page the card was on.
    page: int
    company_id: str
    name: str
    slug: str
    profile_url: str
    #: Clutch's placement label: ``Sponsor``, ``Nearby Sponsor`` or ``Directory``.
    placement: str
    #: Paid placement (``Sponsor`` or ``Nearby Sponsor``).
    sponsored: bool
    rating: float | None = None
    #: 0 for companies that are "Not yet reviewed".
    review_count: int = 0
    #: ``Premier Verified``, ``Verified`` or ``None``.
    verification: str | None = None
    clutch_guarantee: bool = False
    min_project_size: str | None = None
    min_project_size_usd: int | None = None
    hourly_rate: str | None = None
    hourly_rate_min: int | None = None
    hourly_rate_max: int | None = None
    employees: str | None = None
    employees_min: int | None = None
    employees_max: int | None = None
    #: Location as shown on the card ("Paramus, NJ"). With a location filter this is
    #: the office nearest to it; "Serves ..." marks a nearby sponsor.
    location: str | None = None
    #: Headquarters address (from the card's structured data, when Clutch includes it).
    hq_street_address: str | None = None
    hq_city: str | None = None
    hq_region: str | None = None
    hq_postal_code: str | None = None
    hq_country: str | None = None
    phone: str | None = None
    services: list[ServiceShare] = field(default_factory=list)
    #: Clutch's summary of the company and its reviews.
    description: str | None = None
    #: Clutch's insight tabs: review themes ("Collaborative"), "Experience in 9
    #: industries", "4.9 out of 5.0 rating for cost", ...
    highlights: list[str] = field(default_factory=list)
    website: str | None = None
    logo: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """A flat row for CSV: the service mix becomes ``"SEO 50% | PPC 30%"``."""
        row = self.to_dict()
        row["services"] = " | ".join(share_label(s) for s in self.services)
        row["highlights"] = " | ".join(self.highlights)
        return row


def share_label(share: ServiceShare) -> str:
    """``"Search Engine Optimization 50%"``."""
    return f"{share.name} {share.percent}%" if share.percent is not None else share.name


@dataclass
class DirectoryPage:
    """One page of a directory listing."""

    url: str
    page: int
    title: str | None
    heading: str | None
    #: Companies matching the filters (the "83,979 Companies" counter).
    total: int | None
    companies: list[Company]
    #: Filters Clutch applied, ``{name: [values]}`` (the page's own echo).
    applied_filters: dict[str, list[str]] = field(default_factory=dict)
    #: Labels of the applied filter values, ``{name: [labels]}``.
    applied_labels: dict[str, list[str]] = field(default_factory=dict)
    #: The URL Clutch normalised the request to (shows sort and SEO paths).
    clutch_url: str | None = None
    canonical_url: str | None = None
    has_next: bool = False


@dataclass
class SearchResults:
    """Everything :meth:`~clutch_scraper.Clutch.search` collected."""

    url: str
    total: int | None
    companies: list[Company]
    pages_fetched: int
    applied_filters: dict[str, list[str]] = field(default_factory=dict)
    applied_labels: dict[str, list[str]] = field(default_factory=dict)
    #: Requested ``(name, value)`` filters that Clutch did not apply.
    ignored_filters: list[tuple[str, str]] = field(default_factory=list)
    heading: str | None = None


@dataclass
class Location:
    """A place Clutch can filter by (from its location autocomplete)."""

    location_id: int
    name: str
    #: ``CITY``, ``PROVINCE``, ``COUNTRY``, ...
    type: str | None = None
    #: Companies Clutch lists for the place (all directories).
    company_count: int | None = None
    population: int | None = None
    has_companies: bool = True


@dataclass
class FilterChoice:
    label: str
    value: str
    count: int | None = None


@dataclass
class FilterOptions:
    """One filter menu of a directory (``hourly_rate``, ``industries``, ...)."""

    name: str
    type: str | None
    choices: list[FilterChoice] = field(default_factory=list)
    #: The menu title for grouped focus areas ("SEO Focus").
    title: str | None = None


@dataclass
class QA:
    """One question and answer from a review interview."""

    section: str
    question: str
    answer: str


@dataclass
class Review:
    """A client review from a company profile."""

    review_id: str
    title: str | None = None
    #: Pinned "Featured Review" (shown first on page 1).
    featured: bool = False
    date: str | None = None
    date_label: str | None = None
    rating: float | None = None
    quality: float | None = None
    schedule: float | None = None
    cost: float | None = None
    willing_to_refer: float | None = None
    services: list[str] = field(default_factory=list)
    project_size: str | None = None
    project_length: str | None = None
    quote: str | None = None
    summary: str | None = None
    feedback: str | None = None
    reviewer_title: str | None = None
    reviewer_name: str | None = None
    reviewer_industry: str | None = None
    reviewer_location: str | None = None
    reviewer_company_size: str | None = None
    #: ``Online Review``, ``Phone Interview``, ...
    review_type: str | None = None
    #: Background, challenge, solution and results interview answers.
    interview: list[QA] = field(default_factory=list)
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """A flat row for CSV: services joined, the interview as ``Q: ... A: ...`` text."""
        row = self.to_dict()
        row["services"] = " | ".join(self.services)
        row["interview"] = "\n\n".join(f"Q: {qa.question}\nA: {qa.answer}" for qa in self.interview)
        return row


@dataclass
class ReviewsPage:
    """One page of a company's reviews."""

    url: str
    page: int
    reviews: list[Review]
    #: Reviews matching the review filters ("Showing 1-10 of 370 Reviews").
    total: int | None = None
    #: Review filters as Clutch applied them (sort, page, cost, ...).
    applied: dict[str, Any] = field(default_factory=dict)
    last_page: int | None = None


@dataclass
class Office:
    """One office from the profile's location list."""

    headquarters: bool
    street_address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    postal_code: str | None = None
    employees: str | None = None
    phone: str | None = None


@dataclass
class Package:
    """A fixed-price package listed on the profile."""

    name: str
    description: str | None = None
    currency: str | None = None
    low_price: float | None = None
    high_price: float | None = None
    tiers: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Profile:
    """A company profile page."""

    slug: str
    url: str
    name: str
    company_id: str | None = None
    tagline: str | None = None
    description: str | None = None
    website: str | None = None
    logo: str | None = None
    rating: float | None = None
    review_count: int = 0
    verification: str | None = None
    clutch_guarantee: bool = False
    claimed: bool = True
    min_project_size: str | None = None
    min_project_size_usd: int | None = None
    hourly_rate: str | None = None
    hourly_rate_min: int | None = None
    hourly_rate_max: int | None = None
    employees: str | None = None
    employees_min: int | None = None
    employees_max: int | None = None
    founded: int | None = None
    headquarters: str | None = None
    phone: str | None = None
    languages: list[str] = field(default_factory=list)
    timezones: list[str] = field(default_factory=list)
    offices: list[Office] = field(default_factory=list)
    service_lines: list[ServiceShare] = field(default_factory=list)
    #: Focus areas per group: ``{"SEO Focus": [ServiceShare, ...]}``.
    focus: dict[str, list[ServiceShare]] = field(default_factory=dict)
    industries: list[ServiceShare] = field(default_factory=list)
    clients: list[ServiceShare] = field(default_factory=list)
    #: Clutch credentials such as "Clutch Certified - Search Engine Optimization".
    certifications: list[str] = field(default_factory=list)
    rating_for_cost: float | None = None
    common_project_size: str | None = None
    packages: list[Package] = field(default_factory=list)
    #: The Verification section: ``{"Business Entity": {"Status": "Active", ...}, ...}``.
    verification_details: dict[str, dict[str, str]] = field(default_factory=dict)
    social: dict[str, str] = field(default_factory=dict)
    #: The first page of reviews (Clutch's default order).
    reviews: list[Review] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """A flat row for CSV (one per company; reviews are left out)."""
        row = self.to_dict()
        row.pop("reviews")
        for key in ("service_lines", "industries", "clients"):
            row[key] = " | ".join(share_label(s) for s in getattr(self, key))
        row["focus"] = " | ".join(
            f"{group}: " + ", ".join(share_label(s) for s in shares)
            for group, shares in self.focus.items()
        )
        row["offices"] = " | ".join(
            ", ".join(p for p in (o.city, o.region, o.country) if p) for o in self.offices
        )
        return row
