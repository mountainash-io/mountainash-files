"""Quote-aware logical record scanning and tokenization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mountainash_files.formats._exceptions import ParseError

if TYPE_CHECKING:
    from mountainash_files.formats.csv import CsvSpec


def scan_logical_records(text: str, spec: "CsvSpec") -> tuple[str, ...]:
    """Split only at unquoted, unescaped line terminators."""
    _validate_delimited_spec(spec)
    records: list[str] = []
    start = 0
    index = 0
    quoted = False
    while index < len(text):
        if spec.quote_char is not None and text.startswith(spec.quote_char, index):
            if quoted and spec.double_quote and text.startswith(spec.quote_char * 2, index):
                index += 2
                continue
            if quoted and spec.escape_char is not None and index > 0 and text[index - 1] == spec.escape_char:
                index += 1
                continue
            quoted = not quoted
            index += 1
            continue
        if not quoted and text.startswith(spec.line_terminator, index):
            records.append(text[start:index])
            index += len(spec.line_terminator)
            start = index
            continue
        index += 1
    if quoted:
        raise ParseError("csv", "unterminated quoted field")
    if start < len(text):
        records.append(text[start:])
    return tuple(records)


def remove_comment_records(records: tuple[str, ...], spec: "CsvSpec") -> tuple[str, ...]:
    """Remove true comment records before header and field processing."""
    retained = [
        record
        for number, record in enumerate(records, start=1)
        if number not in set(spec.comment_rows)
        and not (spec.comment_char is not None and record.startswith(spec.comment_char))
    ]
    return tuple(retained)


def tokenize_record(record: str, spec: "CsvSpec") -> tuple[str | None, ...]:
    """Apply delimiter, quote, escaping, initial-space, and null handling."""
    _validate_delimited_spec(spec)
    values: list[str | None] = []
    field: list[str] = []
    index = 0
    quoted = False
    after_delimiter = True
    while index < len(record):
        if spec.quote_char is not None and record.startswith(spec.quote_char, index):
            if quoted and spec.double_quote and record.startswith(spec.quote_char * 2, index):
                field.append(spec.quote_char)
                index += 2
                continue
            if quoted and spec.escape_char is not None and index > 0 and record[index - 1] == spec.escape_char:
                field[-1:] = [spec.quote_char]
                index += 1
                continue
            quoted = not quoted
            index += 1
            after_delimiter = False
            continue
        if not quoted and record.startswith(spec.delimiter, index):
            values.append(_normalize_field("".join(field), spec))
            field = []
            index += len(spec.delimiter)
            after_delimiter = True
            continue
        if after_delimiter and spec.skip_initial_space and record[index] == " ":
            index += 1
            continue
        field.append(record[index])
        after_delimiter = False
        index += 1
    if quoted:
        raise ParseError("csv", "unterminated quoted field")
    values.append(_normalize_field("".join(field), spec))
    return tuple(values)


def _normalize_field(value: str, spec: "CsvSpec") -> str | None:
    return None if spec.null_sequence is not None and value == spec.null_sequence else value


def _validate_delimited_spec(spec: "CsvSpec") -> None:
    if not spec.delimiter:
        raise ParseError("csv", "delimiter cannot be empty")
    if not spec.line_terminator:
        raise ParseError("csv", "line terminator cannot be empty")
