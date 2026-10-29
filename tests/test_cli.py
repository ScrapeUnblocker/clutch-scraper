from __future__ import annotations

import csv
import json

import pytest
from conftest import FakeClient, by_url, fixture_text

from clutch_scraper import Clutch, cli
from clutch_scraper.export import format_for, render


@pytest.fixture
def fake_api(monkeypatch, directory_html, profile_html, reviews_html):
    """Route the CLI's Clutch through a fake client answering from the fixtures."""
    client = FakeClient(
        by_url(
            {
                "/directory/locations": fixture_text("locations.json"),
                "/directory/facets": fixture_text("facets.html"),
                "/profile/smartsites?": reviews_html,
                "/profile/": profile_html,
            },
            default=directory_html,
        )
    )

    def factory(**kwargs):
        return Clutch(client=client, sleep=lambda s: None, **kwargs)

    monkeypatch.setattr(cli, "Clutch", factory)
    return client


def test_parser_search_options():
    args = cli.build_parser().parse_args(
        [
            "search",
            "seo-firms",
            "--location",
            "London",
            "--hourly-rate",
            "50-99,100-149",
            "--hourly-rate",
            "150-199",
            "--size",
            "10-49",
            "--min-reviews",
            "10",
            "--budget",
            "25000",
            "--sort",
            "rating",
            "--verified",
            "--param",
            "specializations=field_accessibility",
            "-p",
            "2",
            "-n",
            "30",
            "--organic",
        ]
    )
    filters = cli.directory_filters(args, 9307)
    assert filters.hourly_rates == ["50-99", "100-149", "150-199"]
    assert ("specializations", "field_accessibility") in filters.to_params()
    assert (args.pages, args.limit, args.organic, args.min_reviews) == (2, 30, True, 10)


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "seo-firms", "--min-reviews", "4"],
        ["search", "seo-firms", "--pages", "0"],
        ["search", "seo-firms", "--param", "novalue"],
        ["search", "seo-firms", "--location", "x", "--location-id", "1"],
        ["reviews", "smartsites", "--sort", "oldest"],
        ["profile"],
    ],
)
def test_parser_rejects(argv):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(argv)


def test_search_to_csv(fake_api, tmp_path, capsys):
    out = tmp_path / "companies.csv"
    code = cli.main(["search", "seo-firms", "--location", "London", "--organic", "-o", str(out)])
    assert code == 0
    assert fake_api.urls[0].endswith("/directory/locations?q=London")
    assert "geona_id=9307" in fake_api.urls[1]
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["name"] for r in rows] == ["Fannit", "ConnectNC, Inc."]
    assert rows[0]["services"].endswith("%")
    err = capsys.readouterr().err
    assert "location: London, England (id 9307" in err
    assert "1,698 companies; 2 collected from 1 page(s)" in err
    assert "ignored the filter geona_id=9307" in err  # the fixture echoes New York


def test_search_table(fake_api, capsys):
    assert cli.main(["search", "seo-firms", "-n", "2", "-f", "table"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split()[:4] == ["rank", "name", "rating", "review_count"]
    assert "SmartSites" in out[1] and len(out) == 3


def test_profile_json(fake_api, capsys):
    assert cli.main(["profile", "smartsites"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "SmartSites" and data["offices"][0]["city"] == "Paramus"


def test_reviews_jsonl(fake_api, tmp_path):
    out = tmp_path / "reviews.jsonl"
    code = cli.main(["reviews", "smartsites", "--sort", "newest", "-n", "2", "-o", str(out)])
    assert code == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["review_id"] == "417100"
    assert "sort_by=date_desc" in fake_api.urls[0]


def test_locations_and_filters(fake_api, capsys):
    assert cli.main(["locations", "London", "-f", "table"]) == 0
    assert "Londonderry, New Hampshire" in capsys.readouterr().out
    assert cli.main(["filters", "seo-firms", "--name", "hourly_rate", "-f", "csv"]) == 0
    rows = list(csv.DictReader(capsys.readouterr().out.splitlines()))
    assert {r["filter"] for r in rows} == {"hourly_rate"}
    assert rows[0]["value"] == "0-25"


def test_errors_exit_with_1(fake_api, capsys):
    assert cli.main(["search", "seo-firms", "--size", "huge"]) == 1
    assert "unknown company size" in capsys.readouterr().err
    assert cli.main(["search", "https://example.com/seo-firms"]) == 1
    assert "not a clutch.co URL" in capsys.readouterr().err


def test_format_for_and_render():
    assert format_for("out.csv", None) == "csv"
    assert format_for("out.JSONL", None) == "jsonl"
    assert format_for("out.txt", None) == "json"
    assert format_for("out.csv", "table") == "table"
    assert render([], "table") == "(no results)\n"
    assert render([{"a": [1, 2], "b": {"c": 1}}], "csv") == 'a,b\n1 | 2,"{""c"": 1}"\n'
    with pytest.raises(ValueError):
        render([], "xml")
