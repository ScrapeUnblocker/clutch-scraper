from __future__ import annotations

import pytest
from conftest import fixture_text

from clutch_scraper import NotFoundError, ParseError
from clutch_scraper.parsing import (
    parse_directory,
    parse_facets,
    parse_locations,
    parse_profile,
    parse_reviews,
    real_website,
    window_json,
)


def test_directory_page(directory_html):
    page = parse_directory(directory_html, url="u", page=3)
    assert page.total == 1698  # the directory counter, not the Leaders Matrix one
    assert page.heading == "Top SEO Companies in New York City"
    assert page.applied_filters == {"geona_id": ["26002"]}
    assert page.applied_labels == {"geona_id": ["New York City, New York"]}
    assert page.clutch_url == "https://clutch.co/seo-firms/new-york?sort_by=ClutchRank"
    assert page.has_next  # the pager goes to page 4
    assert not parse_directory(directory_html, page=4).has_next
    # the repeated sponsor card is dropped
    assert [c.name for c in page.companies] == [
        "SmartSites",
        "SEO Brand",
        "Fannit",
        "ConnectNC, Inc.",
    ]


def test_sponsored_card_with_address(directory_html):
    company = parse_directory(directory_html).companies[0]
    assert company.company_id == "188351"
    assert company.slug == "smartsites"
    assert company.profile_url == "https://clutch.co/profile/smartsites"
    assert (company.placement, company.sponsored) == ("Sponsor", True)
    assert (company.rating, company.review_count) == (4.9, 370)
    assert company.verification == "Premier Verified"
    assert company.min_project_size == "$1,000+"
    assert company.min_project_size_usd == 1000
    assert (company.hourly_rate_min, company.hourly_rate_max) == (100, 149)
    assert (company.employees_min, company.employees_max) == (250, 999)
    assert company.location == "Paramus, NJ"
    assert (company.hq_city, company.hq_region, company.hq_country) == ("Paramus", "NJ", "US")
    assert company.hq_postal_code == "07652"
    assert [(s.name, s.percent) for s in company.services][:2] == [
        ("Search Engine Optimization", 50),
        ("Pay Per Click", 30),
    ]
    assert company.website == "https://smartsites.com/lp/digital-marketing-lp/"  # utm_* removed
    assert company.description and not company.description.endswith("Show More")
    assert company.logo.startswith("https://")


def test_nearby_sponsor_and_organic_cards(directory_html):
    _, nearby, organic, unreviewed = parse_directory(directory_html).companies
    assert nearby.placement == "Nearby Sponsor" and nearby.sponsored
    assert nearby.location == "Serves New York City, NY"
    assert nearby.clutch_guarantee
    assert organic.placement == "Directory" and not organic.sponsored
    assert organic.highlights[:1] == ["Collaborative"]
    assert organic.website == "https://fannit.com/"
    assert unreviewed.rating is None and unreviewed.review_count == 0
    assert unreviewed.hourly_rate == "Undisclosed"
    assert unreviewed.hourly_rate_min is None and unreviewed.min_project_size_usd is None
    assert unreviewed.website is None
    assert len(unreviewed.services) == 5


def test_company_rows_flatten_services(directory_html):
    row = parse_directory(directory_html).companies[0].to_row()
    assert row["services"].startswith("Search Engine Optimization 50% | Pay Per Click 30%")


def test_page_past_the_end(past_end_html):
    page = parse_directory(past_end_html, page=5)
    assert page.companies == [] and page.total == 0 and not page.has_next


def test_not_a_directory():
    with pytest.raises(ParseError):
        parse_directory("<html><body><h1>Something else</h1></body></html>")


def test_profile(profile_html):
    profile = parse_profile(profile_html)
    assert (profile.slug, profile.name, profile.company_id) == (
        "smartsites",
        "SmartSites",
        "188351",
    )
    assert profile.url == "https://clutch.co/profile/smartsites"
    assert profile.website == "https://www.smartsites.com/lp/digital-marketing-lp/"
    assert (profile.rating, profile.review_count) == (4.9, 370)
    assert profile.verification == "Premier Verified"
    assert profile.claimed
    assert profile.tagline.startswith("Think Web. Think Smart.")
    assert (
        "- Search Engine Optimization (SEO)\n  - On-page and technical SEO" in profile.description
    )
    assert (profile.founded, profile.headquarters) == (2011, "Paramus, NJ")
    assert (profile.hourly_rate_min, profile.hourly_rate_max) == (100, 149)
    assert profile.min_project_size_usd == 1000
    assert profile.languages == ["English", "Spanish"]
    assert profile.timezones == ["Eastern Standard Time (EST)"]
    assert profile.phone == "2018706000"


def test_profile_offices(profile_html):
    hq, branch, other = parse_profile(profile_html).offices
    assert hq.headquarters
    assert (hq.street_address, hq.city, hq.region, hq.postal_code) == (
        "45 Eisenhower Drive",
        "Paramus",
        "NJ",
        "07652",
    )
    assert (hq.country, hq.employees, hq.phone) == ("United States", "50 - 75", "2018706000")
    assert not branch.headquarters
    assert (branch.city, branch.region, branch.country) == ("Chamblee", "GA", "United States")
    assert (other.city, other.street_address, other.postal_code) == (
        "San Antonio",
        "2186 Jackson Keller Road",
        "78213",
    )


def test_profile_charts_pricing_and_verification(profile_html):
    profile = parse_profile(profile_html)
    assert [(s.name, s.percent) for s in profile.service_lines][0] == (
        "Search Engine Optimization",
        50,
    )
    assert profile.service_lines[0].url == "https://clutch.co/seo-firms"
    assert "SEO Focus" in profile.focus
    assert [s.name for s in profile.clients] == ["Small Business (<$10M)", "Midmarket ($10M - $1B)"]
    assert profile.industries and profile.industries[0].percent == 15
    assert profile.certifications[0] == "Clutch Premier Verified"
    assert profile.rating_for_cost == 4.9
    assert profile.common_project_size == "$10,000 - $49,999"
    package = profile.packages[0]
    assert (package.currency, package.low_price, package.high_price) == ("USD", 1250.0, 4000.0)
    assert [t["name"] for t in package.tiers] == [
        "Small Package",
        "Medium Package",
        "Large Package",
    ]
    assert profile.verification_details["Business Entity"]["Status"] == "Active"
    assert profile.verification_details["Summary"]["Verified Client Reviews"] == "289"
    assert profile.social["LinkedIn"] == "https://www.linkedin.com/company/smartsites/"


def test_profile_reviews(profile_html):
    featured, review = parse_profile(profile_html).reviews
    assert featured.featured and featured.review_id == "320820"
    assert not review.featured
    assert review.review_id == "180295"
    assert review.title == "PPC Services for Ski Gear, Apparel & Accessories Company"
    assert (review.date, review.date_label) == ("2023-02-09", "Feb 9, 2023")
    assert (review.rating, review.quality, review.cost, review.willing_to_refer) == (5, 5, 5, 5)
    assert review.services == ["Pay Per Click", "Search Engine Optimization"]
    assert (review.project_size, review.project_length) == (
        "Less than $10,000",
        "Aug. 2022 - Ongoing",
    )
    assert review.quote.startswith("They have great communication")
    assert review.reviewer_title == "Manager, Ski Apparel & Accessories Company"
    assert (review.reviewer_industry, review.reviewer_location) == (
        "Retail",
        "Pittsburgh, Pennsylvania",
    )
    assert (review.reviewer_company_size, review.review_type) == ("1-10 Employees", "Online Review")
    assert review.summary.startswith("SmartSites provides PPC services")
    sections = [qa.section for qa in review.interview]
    assert sections[0] == "Background" and "Results & Feedback" in sections
    assert review.interview[0].answer == "Manager"
    assert review.url.endswith("/180295")
    assert "Q: Please describe your company" in review.to_row()["interview"]


def test_unclaimed_profile_without_reviews():
    profile = parse_profile(fixture_text("profile_unclaimed.html"))
    assert profile.name == "ConnectNC, Inc." and not profile.claimed
    assert profile.rating is None and profile.review_count == 0 and profile.reviews == []
    assert profile.hourly_rate == "Undisclosed" and profile.hourly_rate_min is None
    assert profile.founded == 1996
    assert profile.offices[0].city == "Southern Pines"
    assert profile.website == "https://www.connectnc.com/"
    assert set(profile.focus) == {"CMS Focus", "IT Managed Services Focus"}
    assert profile.verification_details == {}


def test_profile_missing(past_end_html):
    with pytest.raises(NotFoundError):
        parse_profile(past_end_html)


def test_reviews_page(reviews_html):
    page = parse_reviews(reviews_html, page=2)
    assert page.total == 111
    assert page.last_page == 12
    assert page.applied["SortBy"] == 1 and page.applied["PageNum"] == 1
    dates = [r.date for r in page.reviews]
    assert dates == sorted(dates, reverse=True)
    assert {r.project_size for r in page.reviews} == {"$10,000 to $49,999"}


def test_locations():
    locations = parse_locations(fixture_text("locations.json"))
    assert [(x.location_id, x.name, x.type) for x in locations[:3]] == [
        (9307, "London, England", "CITY"),
        (3768, "London, Ontario", "CITY"),
        (44045, "Londonderry, New Hampshire", "CITY"),
    ]
    assert locations[0].company_count == 13802
    wrapped = "<html><body><pre>" + fixture_text("locations.json") + "</pre></body></html>"
    assert parse_locations(wrapped)[0].location_id == 9307
    with pytest.raises(ParseError):
        parse_locations("<html>blocked</html>")


def test_facets():
    options = {o.name: o for o in parse_facets(fixture_text("facets.html"))}
    assert "geona_id" not in options  # no choices
    assert [c.value for c in options["hourly_rate"].choices][:2] == ["0-25", "25-49"]
    assert options["hourly_rate"].choices[0].label == "< $25"
    assert options["hourly_rate"].choices[0].count == 10475
    assert options["sort_by"].choices[2].value == "ClutchRank"
    assert all(c.value != "-1" for c in options["specializations"].choices)
    assert options["group_pp_seo_group"].title == "SEO Focus"
    assert options["group_pp_seo_group"].choices[0].value == "field_pp_seo_content_synd"


def test_real_website():
    redirect = (
        "https://r.clutch.co/redirect?event_label=1&u=https%3A%2F%2Fwww.example.com%2Fpage"
        "%3Futm_source%3Dclutch.co%26ref%3D7%26utm_medium%3Dreferral"
    )
    assert real_website(redirect) == "https://www.example.com/page?ref=7"
    assert real_website("https://example.org/") == "https://example.org/"
    assert real_website("https://r.clutch.co/redirect?x=1") is None
    assert real_website("#") is None
    assert real_website(None) is None


def test_window_json():
    html = '<script>window.a = {"x": [1, 2]}; window.b = {"y": "};"};</script>'
    assert window_json(html, "a") == {"x": [1, 2]}
    assert window_json(html, "b") == {"y": "};"}
    assert window_json(html, "missing") is None
