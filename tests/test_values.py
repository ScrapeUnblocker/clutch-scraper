from __future__ import annotations

import pytest

from clutch_scraper import values as v


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("$100 - $149 / hr", (100, 149)),
        ("$300+ / hr", (300, None)),
        ("< $25 / hr", (None, 25)),
        ("250 - 999", (250, 999)),
        ("1,000 - 9,999", (1000, 9999)),
        ("10,000+", (10000, None)),
        ("Freelancer", (1, 1)),
        ("Undisclosed", (None, None)),
        (None, (None, None)),
        ("", (None, None)),
    ],
)
def test_int_range(label, expected):
    assert v.int_range(label) == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [("$1,000+", 1000), ("$25,000+", 25000), ("Undisclosed", None), (None, None)],
)
def test_money_floor(label, expected):
    assert v.money_floor(label) == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Feb 9, 2023", "2023-02-09"),
        ("October 28, 2026", "2026-10-28"),
        ("Sept. 3, 2025", "2025-09-03"),
        ("Aug. 2022", "2022-08"),
        ("not a date", None),
        (None, None),
    ],
)
def test_iso_date(label, expected):
    assert v.iso_date(label) == expected


def test_numbers_and_clean():
    assert v.to_int("370\n   reviews") == 370
    assert v.to_float("4.9") == 4.9
    assert v.to_int("no digits") is None
    assert v.clean("  a \n\t b  ") == "a b"
    assert v.clean("   ") is None
