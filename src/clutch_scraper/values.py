"""Turn Clutch's display strings into numbers and ISO dates.

Clutch shows most facts as text: ``$1,000+`` (min project size), ``$100 - $149 / hr``
(hourly rate), ``250 - 999`` (employees), ``Feb 9, 2023`` (review date). These helpers
keep the original label and add the numbers you can sort and filter on.
"""

from __future__ import annotations

import re
from datetime import datetime

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SPACE = re.compile(r"\s+")
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%b %Y", "%B %Y")
#: Clutch writes "Sept." where strptime expects "Sep".
_MONTH_FIXES = {"Sept": "Sep"}


def clean(text: str | None) -> str | None:
    """``text`` with runs of whitespace collapsed, or ``None`` when empty."""
    if text is None:
        return None
    text = _SPACE.sub(" ", text).strip()
    return text or None


def numbers(text: str | None) -> list[float]:
    """Every number in ``text`` (thousands separators removed)."""
    return [float(m.replace(",", "")) for m in _NUMBER.findall(text or "")]


def to_int(text: str | None) -> int | None:
    """The first whole number in ``text``: ``"370 reviews"`` -> ``370``."""
    found = numbers(text)
    return int(found[0]) if found else None


def to_float(text: str | None) -> float | None:
    """The first number in ``text``: ``"4.9"`` -> ``4.9``."""
    found = numbers(text)
    return found[0] if found else None


def is_undisclosed(text: str | None) -> bool:
    return not text or text.strip().lower() in {"undisclosed", "n/a", "-"}


def int_range(text: str | None) -> tuple[int | None, int | None]:
    """The bounds of a Clutch range label.

    ``"$100 - $149 / hr"`` -> ``(100, 149)``, ``"$300+ / hr"`` -> ``(300, None)``,
    ``"< $25 / hr"`` -> ``(None, 25)``, ``"10,000+"`` -> ``(10000, None)``,
    ``"Freelancer"`` -> ``(1, 1)`` and ``"Undisclosed"`` -> ``(None, None)``.
    """
    if text is None or is_undisclosed(text):
        return None, None
    if text.strip().lower().startswith("freelance"):
        return 1, 1
    found = [int(n) for n in numbers(text)]
    if not found:
        return None, None
    if len(found) >= 2:
        return found[0], found[1]
    if "<" in text or "under" in text.lower() or "less than" in text.lower():
        return None, found[0]
    if "+" in text:
        return found[0], None
    return found[0], found[0]


def money_floor(text: str | None) -> int | None:
    """The amount in a minimum-size label: ``"$1,000+"`` -> ``1000``."""
    if is_undisclosed(text):
        return None
    return to_int(text)


def percent(text: str | None) -> int | None:
    """``"50%"`` -> ``50``."""
    return to_int(text)


def iso_date(text: str | None) -> str | None:
    """A Clutch date as ``YYYY-MM-DD`` (``YYYY-MM`` for month-only dates).

    ``"Feb 9, 2023"`` -> ``"2023-02-09"``, ``"October 28, 2026"`` -> ``"2026-10-28"``,
    ``"Aug. 2022"`` -> ``"2022-08"``. Unknown formats return ``None``.
    """
    value = clean(text)
    if not value:
        return None
    value = value.replace(".", "")
    for wrong, right in _MONTH_FIXES.items():
        value = re.sub(rf"\b{wrong}\b", right, value)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%d" if "%d" in fmt else "%Y-%m")
    return None
