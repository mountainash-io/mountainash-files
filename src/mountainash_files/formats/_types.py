from __future__ import annotations

import dataclasses
from typing import Any, ClassVar


class FormatSpec:
    """Base for all format specifications.

    Subclasses must be @dataclass(frozen=True) and declare FORMAT and SUFFIXES.
    """

    FORMAT: ClassVar[str]
    SUFFIXES: ClassVar[tuple[str, ...]]


@dataclasses.dataclass(frozen=True)
class ParseResult:
    """Typed wrapper around parsed data."""

    data: Any
    format_key: str
    spec: FormatSpec
