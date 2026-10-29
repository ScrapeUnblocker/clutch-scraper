from __future__ import annotations

import pytest

from clutch_scraper.urls import (
    directory_path,
    directory_url,
    facets_url,
    locations_url,
    profile_slug,
    profile_url,
)


@pytest.mark.parametrize(
    "value",
    ["seo-firms", "/seo-firms", "seo-firms/", "https://clutch.co/seo-firms", "clutch.co/seo-firms"],
)
def test_directory_path_forms(value):
    assert directory_path(value) == ("/seo-firms", [])


def test_directory_path_keeps_query_but_drops_page():
    path, params = directory_path(
        "https://clutch.co/agencies/digital-marketing?hourly_rate=50-99&hourly_rate=100-149&page=3"
    )
    assert path == "/agencies/digital-marketing"
    assert params == [("hourly_rate", "50-99"), ("hourly_rate", "100-149")]


@pytest.mark.parametrize(
    "value", ["", "/", "https://example.com/seo-firms", "https://clutch.co/profile/smartsites"]
)
def test_directory_path_rejects(value):
    with pytest.raises(ValueError):
        directory_path(value)


def test_directory_url_paging_skips_the_page_1_alias():
    assert directory_url("/seo-firms") == "https://clutch.co/seo-firms"
    assert directory_url("/seo-firms", page=2) == "https://clutch.co/seo-firms?page=2"
    url = directory_url("/seo-firms", [("agency_size", "10 - 49")], page=3)
    assert url == "https://clutch.co/seo-firms?agency_size=10+-+49&page=3"
    with pytest.raises(ValueError):
        directory_url("/seo-firms", page=0)


@pytest.mark.parametrize(
    "value",
    [
        "smartsites",
        "/profile/smartsites",
        "https://clutch.co/profile/smartsites",
        "https://clutch.co/profile/smartsites?page=2#reviews",
    ],
)
def test_profile_slug(value):
    assert profile_slug(value) == "smartsites"


def test_profile_slug_rejects_paths():
    with pytest.raises(ValueError):
        profile_slug("agencies/seo")
    with pytest.raises(ValueError):
        profile_slug("")


def test_profile_url_with_review_filters():
    assert profile_url("smartsites") == "https://clutch.co/profile/smartsites"
    url = profile_url("smartsites", [("sort_by", "date_desc")], page=2)
    assert url == "https://clutch.co/profile/smartsites?sort_by=date_desc&page=2"


def test_lookup_urls():
    assert locations_url("new york") == "https://clutch.co/directory/locations?q=new+york"
    assert facets_url("/seo-firms") == "https://clutch.co/directory/facets?path=%2Fseo-firms"
