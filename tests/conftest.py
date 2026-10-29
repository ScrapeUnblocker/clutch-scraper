"""Shared test helpers: real (trimmed) clutch.co responses and a fake ScrapeUnblocker client.

The fixtures are real pages cut down to a few elements each:

* ``directory_page.html`` - /seo-firms filtered to New York City: a sponsor, a nearby
  sponsor, an organic company, an unreviewed company and a repeated sponsor card,
  with the filter echo and the pager of page 4 of 4;
* ``directory_past_end.html`` - the "404" page Clutch serves (HTTP 200) past the end;
* ``profile.html`` / ``profile_unclaimed.html`` - a full profile and an unclaimed one;
* ``reviews_page2.html`` - page 2 of a profile's reviews, newest first, $10k-$50k;
* ``locations.json`` and ``facets.html`` - the location and filter-menu lookups.

No test calls the API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from clutch_scraper import Clutch

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``: answers ``get_page_source`` from
    ``respond(url)`` (a body, or an exception to raise) and records every call."""

    def __init__(self, respond: Callable[[str], Any]):
        self.respond = respond
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_page_source(self, url: str, **kwargs: Any) -> str:
        self.calls.append((url, kwargs))
        result = self.respond(url)
        if isinstance(result, BaseException):
            raise result
        return result

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


def sequence(*answers: Any) -> Callable[[str], Any]:
    """A ``respond`` that returns the answers in order (the last one repeats)."""
    queue = list(answers)

    def respond(url: str) -> Any:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return respond


def by_url(routes: dict[str, Any], default: Any = None) -> Callable[[str], Any]:
    """A ``respond`` that picks the answer whose key is a substring of the URL."""

    def respond(url: str) -> Any:
        for key, answer in routes.items():
            if key in url:
                return answer
        if default is None:
            raise AssertionError(f"unexpected URL {url}")
        return default

    return respond


@pytest.fixture
def make_clutch() -> Callable[..., tuple[Clutch, FakeClient]]:
    def make(respond: Callable[[str], Any], **kwargs: Any) -> tuple[Clutch, FakeClient]:
        client = FakeClient(respond)
        kwargs.setdefault("sleep", lambda seconds: None)
        return Clutch(client=client, **kwargs), client

    return make


@pytest.fixture
def directory_html() -> str:
    return fixture_text("directory_page.html")


@pytest.fixture
def past_end_html() -> str:
    return fixture_text("directory_past_end.html")


@pytest.fixture
def profile_html() -> str:
    return fixture_text("profile.html")


@pytest.fixture
def reviews_html() -> str:
    return fixture_text("reviews_page2.html")
