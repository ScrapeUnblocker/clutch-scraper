"""``clutch-scraper`` command line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .errors import ClutchError
from .export import FORMATS, format_for, write
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
from .scraper import Clutch

EXAMPLES = """\
examples:
  clutch-scraper search seo-firms -f table
  clutch-scraper search seo-firms --location "New York City" --sort rating --min-reviews 10 -f table
  clutch-scraper search web-developers --hourly-rate 50-99,100-149 --size 10-49 -p 3 -o devs.csv
  clutch-scraper search agencies/digital-marketing --industry ecommerce --client-type midmarket \\
      --verified --organic --pages 2 -o agencies.jsonl
  clutch-scraper search "https://clutch.co/developers/react-native?hourly_rate=25-49" -f table
  clutch-scraper profile smartsites -o smartsites.json
  clutch-scraper reviews smartsites --sort newest --project-cost 10k-50k --pages 3 -o reviews.csv
  clutch-scraper locations "London" -f table
  clutch-scraper filters seo-firms --name hourly_rate --name industries -f table
"""

SEARCH_COLUMNS = (
    "rank",
    "name",
    "rating",
    "review_count",
    "hourly_rate",
    "min_project_size",
    "employees",
    "location",
    "placement",
)
PROFILE_COLUMNS = (
    "name",
    "rating",
    "review_count",
    "hourly_rate",
    "min_project_size",
    "employees",
    "founded",
    "headquarters",
    "website",
)
REVIEW_COLUMNS = (
    "date",
    "rating",
    "title",
    "project_size",
    "reviewer_title",
    "reviewer_industry",
    "reviewer_location",
)
LOCATION_COLUMNS = ("location_id", "name", "type", "company_count")
FILTER_COLUMNS = ("filter", "label", "value", "count")


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def key_value(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key.strip():
        raise argparse.ArgumentTypeError(f"expected NAME=VALUE, got {text!r}")
    return key.strip(), value.strip()


def _split(values: Sequence[str] | None) -> list[str]:
    """Repeatable, comma-separated option values as one flat list."""
    out: list[str] = []
    for value in values or []:
        out.extend(v.strip() for v in value.split(",") if v.strip())
    return out


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        help="output format (default: from the -o extension, else json)",
    )
    parser.add_argument("-o", "--output", help="write to this file instead of stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clutch-scraper",
        description=(
            "Scrape Clutch.co company directories, profiles and client reviews "
            "with the ScrapeUnblocker API."
        ),
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--country",
        default="us",
        help="proxy country for requests (default: us; 'any' lets the API choose)",
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="retries for a failed request (default: 3)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log requests and retries")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="list companies in a Clutch directory",
        description="List companies in a directory such as seo-firms, web-developers, "
        "agencies/digital-marketing or it-services/msp (or paste a clutch.co listing URL).",
    )
    search.add_argument("directory", help="directory path or clutch.co listing URL")
    where = search.add_mutually_exclusive_group()
    where.add_argument("--location", help="place name, e.g. 'London' or 'New York City'")
    where.add_argument("--location-id", type=int, help="Clutch location id (see 'locations')")
    search.add_argument("--sort", choices=sorted(SORTS), help="Clutch's sort order")
    search.add_argument(
        "--hourly-rate",
        action="append",
        metavar="RATE",
        help=f"hourly rate band(s), comma-separated: {', '.join(HOURLY_RATES)}",
    )
    search.add_argument(
        "--min-reviews", type=int, choices=MIN_REVIEWS, help="at least this many reviews"
    )
    search.add_argument(
        "--budget",
        type=int,
        choices=BUDGETS,
        help="client budget in USD (companies whose minimum project fits under it)",
    )
    search.add_argument(
        "--size",
        action="append",
        metavar="SIZE",
        help=f"company size(s): {', '.join(COMPANY_SIZES)}",
    )
    search.add_argument(
        "--client-type",
        action="append",
        metavar="TYPE",
        help=f"client focus: {', '.join(CLIENT_TYPES)}",
    )
    search.add_argument(
        "--industry", action="append", metavar="SLUG", help="industry focus, e.g. ecommerce"
    )
    search.add_argument(
        "--service", action="append", metavar="SLUG", help="also offers, e.g. web_design"
    )
    search.add_argument(
        "--focus", action="append", metavar="SLUG", help="focus area slug (see 'filters')"
    )
    search.add_argument("--verified", action="store_true", help="only Clutch-verified companies")
    search.add_argument(
        "--clutch-guarantee", action="store_true", help="only companies with the Clutch Guarantee"
    )
    search.add_argument(
        "--param",
        action="append",
        type=key_value,
        metavar="NAME=VALUE",
        help="any other Clutch query parameter",
    )
    search.add_argument("-p", "--pages", type=positive_int, default=1, help="pages to read")
    search.add_argument("--start-page", type=positive_int, default=1, help="first page")
    search.add_argument("-n", "--limit", type=positive_int, help="stop after this many companies")
    search.add_argument("--organic", action="store_true", help="skip sponsored placements")
    search.add_argument("--min-rating", type=float, help="keep companies rated at least this")
    _output_options(search)

    profile = sub.add_parser("profile", help="full company profiles")
    profile.add_argument("companies", nargs="+", metavar="COMPANY", help="slug or profile URL")
    _output_options(profile)

    reviews = sub.add_parser("reviews", help="a company's client reviews")
    reviews.add_argument("company", help="slug or profile URL")
    reviews.add_argument("--sort", choices=list(REVIEW_SORTS), help="review order")
    reviews.add_argument("--project-cost", choices=list(PROJECT_COSTS), help="project size")
    reviews.add_argument("--industry", metavar="SLUG", help="reviewer industry, e.g. retail")
    reviews.add_argument(
        "--service", action="append", metavar="SLUG", help="service in the project, e.g. seo"
    )
    reviews.add_argument("--location-id", type=int, help="reviewer location id")
    reviews.add_argument("-p", "--pages", type=positive_int, default=1, help="pages to read")
    reviews.add_argument("--start-page", type=positive_int, default=1, help="first page")
    reviews.add_argument("-n", "--limit", type=positive_int, help="stop after this many reviews")
    _output_options(reviews)

    locations = sub.add_parser("locations", help="look up Clutch location ids")
    locations.add_argument("query", help="place name")
    _output_options(locations)

    filters = sub.add_parser("filters", help="list a directory's filter values with counts")
    filters.add_argument("directory", help="directory path or clutch.co listing URL")
    filters.add_argument(
        "--name", action="append", help="only these filters (hourly_rate, industries, ...)"
    )
    _output_options(filters)
    return parser


def directory_filters(args: argparse.Namespace, location_id: int | None) -> DirectoryFilters:
    return DirectoryFilters(
        location_id=location_id,
        sort=args.sort,
        hourly_rates=_split(args.hourly_rate),
        min_reviews=args.min_reviews,
        budget=args.budget,
        company_sizes=_split(args.size),
        client_types=_split(args.client_type),
        industries=_split(args.industry),
        services=_split(args.service),
        focus_areas=_split(args.focus),
        verified=args.verified,
        clutch_guarantee=args.clutch_guarantee,
        extra=args.param or [],
    )


def _note(message: str) -> None:
    print(message, file=sys.stderr)


def run_search(clutch: Clutch, args: argparse.Namespace) -> Any:
    location_id = args.location_id
    if args.location:
        place = clutch.resolve_location(args.location)
        location_id = place.location_id
        _note(f"location: {place.name} (id {place.location_id}, {place.type or 'place'})")
    filters = directory_filters(args, location_id)
    filters.to_params()  # validate before spending a request
    result = clutch.search(
        args.directory,
        filters,
        pages=args.pages,
        start_page=args.start_page,
        limit=args.limit,
        organic_only=args.organic,
        min_rating=args.min_rating,
    )
    total = f"{result.total:,}" if result.total is not None else "?"
    _note(
        f"{result.heading or args.directory}: {total} companies; "
        f"{len(result.companies)} collected from {result.pages_fetched} page(s)"
    )
    for name, value in result.ignored_filters:
        _note(f"warning: Clutch ignored the filter {name}={value} (unknown value?)")
    return result.companies


def run_reviews(clutch: Clutch, args: argparse.Namespace) -> Any:
    filters = ReviewFilters(
        sort=args.sort,
        project_cost=args.project_cost,
        industry=args.industry,
        services=_split(args.service),
        location_id=args.location_id,
    )
    filters.to_params()
    return clutch.reviews(
        args.company, filters, pages=args.pages, start_page=args.start_page, limit=args.limit
    )


def run_filters(clutch: Clutch, args: argparse.Namespace, fmt: str) -> Any:
    options = clutch.filter_options(args.directory)
    if args.name:
        wanted = set(_split(args.name))
        options = [o for o in options if o.name in wanted or (o.title or "") in wanted]
    if fmt in {"csv", "table"}:
        return [
            {"filter": o.name, "label": c.label, "value": c.value, "count": c.count}
            for o in options
            for c in o.choices
        ]
    return options


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    fmt = format_for(args.output, args.format)
    country = None if args.country.lower() in {"any", "none", ""} else args.country.lower()
    try:
        clutch = Clutch(proxy_country=country, max_retries=args.retries)
        columns: Sequence[str] | None = None
        if args.command == "search":
            data: Any = run_search(clutch, args)
            columns = SEARCH_COLUMNS
        elif args.command == "profile":
            data = [clutch.profile(c) for c in args.companies]
            if len(data) == 1 and fmt == "json":
                data = data[0]
            columns = PROFILE_COLUMNS
        elif args.command == "reviews":
            data = run_reviews(clutch, args)
            _note(f"{len(data)} review(s)")
            columns = REVIEW_COLUMNS
        elif args.command == "locations":
            data = clutch.find_locations(args.query)
            columns = LOCATION_COLUMNS
        else:
            data = run_filters(clutch, args, fmt)
            columns = FILTER_COLUMNS
        write(data, fmt, args.output, columns=columns)
        if args.output:
            _note(f"wrote {args.output}")
    except (ClutchError, ValueError) as exc:
        _note(f"error: {exc}")
        return 1
    except Exception as exc:  # SDK errors: auth, credits, outages
        _note(f"error: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
