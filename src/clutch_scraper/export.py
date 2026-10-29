"""Write results as JSON, JSON Lines, CSV or a terminal table."""

from __future__ import annotations

import csv
import io
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from typing import Any, TextIO

FORMATS = ("json", "jsonl", "csv", "table")


def as_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if is_dataclass(item) and not isinstance(item, type):
        return asdict(item)
    return dict(item)


def as_row(item: Any) -> dict[str, Any]:
    """The flat form used for CSV and tables."""
    return item.to_row() if hasattr(item, "to_row") else as_dict(item)


def _items(items: Any) -> list[Any]:
    return list(items) if isinstance(items, (list, tuple)) else [items]


def _cell(value: Any) -> Any:
    """A CSV-friendly value: lists of plain values joined with `` | ``, the rest as JSON."""
    if isinstance(value, (list, tuple)):
        if all(not isinstance(v, (dict, list, tuple)) for v in value):
            return " | ".join(str(v) for v in value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else ""
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(v) for v in value)
    return str(value)


def to_json(items: Any) -> str:
    if isinstance(items, (list, tuple)):
        data: Any = [as_dict(i) for i in items]
    else:
        data = as_dict(items)
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_jsonl(items: Any) -> str:
    return "".join(json.dumps(as_dict(i), ensure_ascii=False) + "\n" for i in _items(items))


def to_csv(items: Any) -> str:
    rows = [as_row(i) for i in _items(items)]
    if not rows:
        return ""
    columns: list[str] = []
    for row in rows:
        columns.extend(k for k in row if k not in columns)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in columns})
    return buffer.getvalue()


def to_table(items: Any, columns: Sequence[str] | None = None, width: int = 40) -> str:
    """A compact, human-readable table of ``columns`` (default: the first eight keys)."""
    rows = [as_row(i) for i in _items(items)]
    if not rows:
        return "(no results)\n"
    header = tuple(columns or list(rows[0])[:8])
    body = [tuple(_short(_text(row.get(c)), width) for c in header) for row in rows]
    table = [header, *body]
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in table]
    return "\n".join(lines) + "\n"


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "~"


def render(items: Any, fmt: str = "json", columns: Sequence[str] | None = None) -> str:
    if fmt == "json":
        return to_json(items) + "\n"
    if fmt == "jsonl":
        return to_jsonl(items)
    if fmt == "csv":
        return to_csv(items)
    if fmt == "table":
        return to_table(items, columns)
    raise ValueError(f"unknown format {fmt!r}; choose from: {', '.join(FORMATS)}")


def format_for(path: str | None, fmt: str | None) -> str:
    """``fmt`` if given, else the format implied by the file extension, else JSON."""
    if fmt:
        return fmt
    if path:
        for ext in ("jsonl", "csv", "json"):
            if path.lower().endswith("." + ext):
                return ext
    return "json"


def write(
    items: Any,
    fmt: str = "json",
    path: str | None = None,
    stream: TextIO | None = None,
    columns: Sequence[str] | None = None,
) -> None:
    """Render ``items`` and write them to ``path`` (UTF-8) or ``stream``."""
    text = render(items, fmt, columns)
    if path:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return
    (stream or sys.stdout).write(text)
