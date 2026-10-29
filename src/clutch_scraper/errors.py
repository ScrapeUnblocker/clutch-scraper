"""Errors raised by the scraper."""

from __future__ import annotations


class ClutchError(Exception):
    """Base class for scraper errors."""


class NotFoundError(ClutchError):
    """Clutch answered 404: an unknown directory path or company profile."""


class ParseError(ClutchError):
    """A response did not contain the expected Clutch data."""


class FilterError(ClutchError, ValueError):
    """A filter value Clutch does not accept (the message lists the valid ones)."""
