from __future__ import annotations

from typing import Any, BinaryIO, Protocol, runtime_checkable

from mountainash_files.formats._types import FormatSpec


@runtime_checkable
class FormatParser(Protocol):
    """Parse raw bytes into a format-natural Python object.

    Parsers return the format-natural type (pa.Table for columnar formats,
    dict/list for JSON, etree.Element for XML, anything for custom formats).
    The parse seam — not the parser — normalises tabular output per the
    ``output=`` flag; a parser that already returns pa.Table passes through
    the arrow path for free. Parsers MUST handle both bytes and BinaryIO.
    """

    def __call__(self, data: bytes | BinaryIO, spec: FormatSpec) -> Any: ...


@runtime_checkable
class FormatSerialiser(Protocol):
    """Serialise a Python object into raw bytes."""

    def __call__(self, data: Any, spec: FormatSpec) -> bytes: ...
