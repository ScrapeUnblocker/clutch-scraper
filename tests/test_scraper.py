from __future__ import annotations

import json

import pytest
from conftest import by_url, fixture_text, sequence
from scrapeunblocker.exceptions import (
    AuthenticationError,
    RateLimitError,
    ScrapeTimeoutError,
    TargetNotFoundError,
)

from clutch_scraper import DirectoryFilters, NotFoundError, ParseError, ReviewFilters
from clutch_scraper.parsing import parse_directory
from clutch_scraper.scraper import ignored_filters


def test_retries_transient_errors_with_backoff(make_clutch, directory_html):
    sleeps = []
    clutch, client = make_clutch(
        sequence(
            RateLimitError("slow down", status_code=429),
            ScrapeTimeoutError("timeout"),
            directory_html,
        ),
        sleep=sleeps.append,
        backoff=1.5,
    )
    page = clutch.directory_page("seo-firms")
    assert len(page.companies) == 4
    assert sleeps == [1.5, 3.0]
    assert clutch.requests == 3
    assert client.calls[0] == ("https://clutch.co/seo-firms", {"proxy_country": "us"})


def test_gives_up_after_max_retries(make_clutch):
    clutch, client = make_clutch(
        sequence(RateLimitError("slow down", status_code=429)), max_retries=2
    )
    with pytest.raises(RateLimitError):
        clutch.directory_page("seo-firms")
    assert len(client.calls) == 3


def test_not_found_is_not_retried(make_clutch):
    missing = TargetNotFoundError("gone", status_code=404, origin_status=404)
    clutch, client = make_clutch(sequence(missing))
    with pytest.raises(NotFoundError):
        clutch.profile("no-such-company")
    assert len(client.calls) == 1


def test_auth_errors_are_raised_at_once(make_clutch):
    clutch, client = make_clutch(sequence(AuthenticationError("bad key", status_code=401)))
    with pytest.raises(AuthenticationError):
        clutch.directory_page("seo-firms")
    assert len(client.calls) == 1


def test_bad_page_is_fetched_once_more(make_clutch, directory_html):
    clutch, client = make_clutch(sequence("<html><body>hold on</body></html>", directory_html))
    assert clutch.directory_page("seo-firms").total == 1698
    assert len(client.calls) == 2

    clutch, client = make_clutch(sequence("<html><body>hold on</body></html>"))
    with pytest.raises(ParseError):
        clutch.directory_page("seo-firms")
    assert len(client.calls) == 2


def test_proxy_country_can_be_left_to_the_api(make_clutch, directory_html):
    clutch, client = make_clutch(sequence(directory_html), proxy_country=None)
    clutch.directory_page("seo-firms")
    assert client.calls[0][1] == {}


def test_search_pages_dedupes_and_ranks(make_clutch, directory_html):
    clutch, client = make_clutch(sequence(directory_html))
    result = clutch.search("seo-firms", DirectoryFilters(location_id=26002), pages=3)
    assert client.urls == [
        "https://clutch.co/seo-firms?geona_id=26002",
        "https://clutch.co/seo-firms?geona_id=26002&page=2",
        "https://clutch.co/seo-firms?geona_id=26002&page=3",
    ]
    assert result.pages_fetched == 3
    assert [c.rank for c in result.companies] == [1, 2, 3, 4]
    assert result.total == 1698
    assert result.heading == "Top SEO Companies in New York City"
    assert result.ignored_filters == []


def test_search_stops_past_the_last_page(make_clutch, directory_html, past_end_html):
    clutch, client = make_clutch(sequence(directory_html, past_end_html))
    result = clutch.search("seo-firms", pages=10)
    assert len(client.calls) == 2
    assert len(result.companies) == 4


def test_search_stops_on_the_pager_last_page(make_clutch, directory_html):
    clutch, client = make_clutch(sequence(directory_html))
    clutch.search("seo-firms", pages=10, start_page=3)
    assert [u.rsplit("=", 1)[1] for u in client.urls] == ["3", "4"]


def test_search_limit_organic_and_min_rating(make_clutch, directory_html):
    clutch, client = make_clutch(sequence(directory_html))
    assert [c.name for c in clutch.search("seo-firms", limit=2).companies] == [
        "SmartSites",
        "SEO Brand",
    ]
    organic = clutch.search("seo-firms", organic_only=True).companies
    assert [(c.rank, c.name) for c in organic] == [(1, "Fannit"), (2, "ConnectNC, Inc.")]
    rated = clutch.search("seo-firms", min_rating=4.85).companies
    assert [c.name for c in rated] == ["SmartSites", "SEO Brand"]


def test_search_reports_ignored_filters(make_clutch, directory_html):
    clutch, _ = make_clutch(sequence(directory_html))
    result = clutch.search(
        "https://clutch.co/seo-firms?client_type=field_pp_cs_enterprise",
        DirectoryFilters(location_id=26002, industries=["ecommerce"], sort="rating"),
    )
    assert result.ignored_filters == [
        ("client_type", "field_pp_cs_enterprise"),
        ("industries", "field_pp_if_ecommerce"),
        ("sort_by", "ReviewRating"),
    ]


def test_ignored_filters_accepts_the_echoed_sort(directory_html):
    page = parse_directory(directory_html)
    assert ignored_filters([("sort_by", "ClutchRank"), ("geona_id", "26002")], page) == []


def test_search_with_nothing_found(make_clutch, past_end_html):
    clutch, _ = make_clutch(sequence(past_end_html))
    result = clutch.search("seo-firms", DirectoryFilters(hourly_rates=["300"]))
    assert result.companies == [] and result.total == 0 and result.pages_fetched == 1


def test_invalid_filters_fail_before_any_request(make_clutch, directory_html):
    clutch, client = make_clutch(sequence(directory_html))
    with pytest.raises(ValueError):
        clutch.search("seo-firms", DirectoryFilters(budget=1))
    assert client.calls == []


def test_profile_by_url(make_clutch, profile_html):
    clutch, client = make_clutch(sequence(profile_html))
    profile = clutch.profile("https://clutch.co/profile/smartsites#reviews")
    assert client.urls == ["https://clutch.co/profile/smartsites"]
    assert profile.name == "SmartSites" and len(profile.reviews) == 2


def test_reviews_across_pages(make_clutch, profile_html, reviews_html):
    clutch, client = make_clutch(by_url({"page=": reviews_html}, default=profile_html))
    reviews = clutch.reviews("smartsites", ReviewFilters(sort="newest"), pages=3)
    assert client.urls == [
        "https://clutch.co/profile/smartsites?sort_by=date_desc",
        "https://clutch.co/profile/smartsites?sort_by=date_desc&page=2",
        "https://clutch.co/profile/smartsites?sort_by=date_desc&page=3",
    ]
    ids = [r.review_id for r in reviews]
    assert len(ids) == len(set(ids)) == 5  # page 3 repeats page 2 here: nothing added
    assert clutch.reviews("smartsites", limit=1)[0].featured


def test_reviews_stop_at_the_last_page(make_clutch, reviews_html):
    clutch, client = make_clutch(sequence(reviews_html))
    clutch.reviews("smartsites", pages=5, start_page=12)
    assert len(client.calls) == 1  # page 12 of 12


def test_locations(make_clutch):
    rows = json.loads(fixture_text("locations.json"))
    rows[0]["HasProviders"] = False
    clutch, client = make_clutch(sequence(json.dumps(rows)))
    assert clutch.resolve_location("London").location_id == 3768
    assert client.urls[0] == "https://clutch.co/directory/locations?q=London"
    clutch, _ = make_clutch(sequence("[]"))
    with pytest.raises(NotFoundError):
        clutch.resolve_location("Atlantis")
    with pytest.raises(ValueError):
        clutch.find_locations("  ")


def test_filter_options(make_clutch):
    clutch, client = make_clutch(sequence(fixture_text("facets.html")))
    names = [o.name for o in clutch.filter_options("seo-firms")]
    assert "hourly_rate" in names and "industries" in names
    assert client.urls == ["https://clutch.co/directory/facets?path=%2Fseo-firms"]
    clutch, _ = make_clutch(sequence('<html><script id="response-meta">{}</script></html>'))
    with pytest.raises(NotFoundError):
        clutch.filter_options("not-a-directory")
