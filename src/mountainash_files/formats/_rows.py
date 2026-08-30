"""Shared row and header normalization for tabular file readers."""

from __future__ import annotations

from collections.abc import Sequence

from mountainash_files.formats._exceptions import ParseError


def apply_header_plan(
    rows: Sequence[tuple[str | None, ...]],
    header: bool,
    header_rows: tuple[int, ...],
    header_join: str,
) -> tuple[tuple[str, ...], tuple[tuple[str | None, ...], ...]]:
    """Resolve normalized header rows and return labels plus data rows."""
    if not rows:
        return (), ()
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ParseError("csv", "inconsistent delimited row widths")
    if not header:
        return tuple(f"field{index}" for index in range(1, width + 1)), tuple(rows)
    positions = tuple(sorted(set(header_rows)))
    if not positions:
        positions = (1,)
    if positions[0] < 1 or positions[-1] > len(rows):
        raise ParseError("csv", "header row is outside the available records")
    header_parts = [rows[position - 1] for position in positions]
    labels = tuple(
        header_join.join(str(part) for part in parts if part not in (None, "")) or f"field{index}"
        for index, parts in enumerate(zip(*header_parts), start=1)
    )
    if len(labels) != len(set(labels)):
        raise ParseError("csv", "duplicate final header labels")
    return labels, tuple(row for index, row in enumerate(rows, start=1) if index not in positions)
