from __future__ import annotations

import pytest

from clutch_scraper import DirectoryFilters, FilterError, ReviewFilters
from clutch_scraper.options import normalize_hourly_rate


def test_directory_filters_to_params():
    filters = DirectoryFilters(
        location_id=26002,
        sort="rating",
        hourly_rates=["50-99", "$100-$149"],
        min_reviews=10,
        budget=25000,
        company_sizes=["10-49", "1,000 - 9,999", "freelancer"],
        client_types=["midmarket"],
        industries=["ecommerce", "field_pp_if_retail"],
        services=["web_design"],
        focus_areas=["field_pp_seo_local_search"],
        verified=True,
        clutch_guarantee=True,
        extra=[("specializations", "field_accessibility")],
    )
    assert filters.to_params() == [
        ("geona_id", "26002"),
        ("hourly_rate", "50-99"),
        ("hourly_rate", "100-149"),
        ("reviews", "10"),
        ("client_budget", "25000"),
        ("agency_size", "10 - 49"),
        ("agency_size", "1,000 - 9,999"),
        ("agency_size", "Freelancer"),
        ("client_type", "field_pp_cs_midmarket"),
        ("industries", "field_pp_if_ecommerce"),
        ("industries", "field_pp_if_retail"),
        ("related_services", "field_pp_sl_web_design"),
        ("focus_areas", "field_pp_seo_local_search"),
        ("verification", "true"),
        ("clutch_guarantee", "true"),
        ("sort_by", "ReviewRating"),
        ("specializations", "field_accessibility"),
    ]


def test_empty_filters():
    assert DirectoryFilters().to_params() == []
    assert DirectoryFilters(min_reviews=0).to_params() == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [("50-99", "50-99"), ("$50 - $99", "50-99"), ("300+", "300"), ("<25", "0-25")],
)
def test_normalize_hourly_rate(value, expected):
    assert normalize_hourly_rate(value) == expected


@pytest.mark.parametrize(
    "filters",
    [
        DirectoryFilters(hourly_rates=["40-60"]),
        DirectoryFilters(min_reviews=4),
        DirectoryFilters(budget=12345),
        DirectoryFilters(company_sizes=["huge"]),
        DirectoryFilters(client_types=["government"]),
        DirectoryFilters(sort="popularity"),
    ],
)
def test_bad_values_raise_with_choices(filters):
    with pytest.raises(FilterError, match="choose from"):
        filters.to_params()


def test_review_filters():
    filters = ReviewFilters(
        sort="newest", project_cost="10k-50k", industry="retail", services=["seo"], location_id=7
    )
    assert filters.to_params() == [
        ("sort_by", "date_desc"),
        ("project_cost", "10000"),
        ("industry", "field_pp_if_retail"),
        ("service_provided", "field_pp_sl_seo"),
        ("location", "7"),
    ]
    with pytest.raises(FilterError):
        ReviewFilters(sort="oldest").to_params()
