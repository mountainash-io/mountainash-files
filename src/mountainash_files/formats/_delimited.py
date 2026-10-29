"""Quote-aware logical record scanning and tokenization."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from mountainash_files.formats._exceptions import ParseError

if TYPE_CHECKING:
    from mountainash_files.formats.csv import CsvSpec


def _lex(text: str, spec: CsvSpec) -> Iterator[tuple[str, str, str, bool]]:
    """Yield token kind, raw text, decoded text, and quoted state."""
    _validate_delimited_spec(spec)
    index = 0
    quoted = False
    tokens = sorted(
        (("delimiter", spec.delimiter), ("record", spec.line_terminator)),
        key=lambda pair: len(pair[1]),
        reverse=True,
    )
    while index < len(text):
        if spec.escape_char is not None and text[index] == spec.escape_char:
            if index + 1 == len(text):
                raise ParseError(spec.FORMAT, "dangling escape")
            yield "data", text[index : index + 2], text[index + 1], quoted
            index += 2
            continue
        if spec.quote_char is not None and text[index] == spec.quote_char:
            if (
                quoted
                and spec.double_quote
                and text.startswith(spec.quote_char * 2, index)
            ):
                yield "data", text[index : index + 2], spec.quote_char, True
                index += 2
                continue
            quoted = not quoted
            yield "quote", text[index], "", quoted
            index += 1
            continue
        matched = False
        if not quoted:
            for kind, token in tokens:
                if text.startswith(token, index):
                    yield kind, token, token, False
                    index += len(token)
                    matched = True
                    break
        if not matched:
            yield "data", text[index], text[index], quoted
            index += 1
    if quoted:
        raise ParseError(spec.FORMAT, "unterminated quoted field")


def iter_logical_records(text: str, spec: "CsvSpec") -> Iterator[tuple[str, int]]:
    """Yield (record, end_offset), splitting only at unquoted, unescaped terminators.

    end_offset is the index in *text* just after the record's terminator, or len(text).
    """
    current: list[str] = []
    position = 0
    for kind, raw, _, _ in _lex(text, spec):
        position += len(raw)
        if kind == "record":
            yield "".join(current), position
            current = []
        else:
            current.append(raw)
    if current:
        yield "".join(current), position


def remove_comment_records(
    records: tuple[str, ...], spec: "CsvSpec"
) -> tuple[str, ...]:
    """Remove true comment records before header and field processing."""
    retained = [
        record
        for number, record in enumerate(records, start=1)
        if number not in set(spec.comment_rows)
        and not (spec.comment_char is not None and record.startswith(spec.comment_char))
    ]
    return tuple(retained)


def tokenize_record_quoted(record: str, spec: "CsvSpec") -> tuple[tuple[str, bool], ...]:
    """Fields as (text, was_quoted); no null normalisation."""
    values: list[tuple[str, bool]] = []
    field: list[str] = []
    quoted_field = False
    at_start = True
    for kind, raw, value, quoted in _lex(record, spec):
        if kind == "delimiter":
            values.append(("".join(field), quoted_field))
            field, quoted_field, at_start = [], False, True
        elif kind == "quote":
            quoted_field, at_start = True, False
        elif kind == "record":
            raise ParseError(spec.FORMAT, "unescaped record terminator inside record")
        else:
            if at_start and not quoted and raw == value == " " and spec.skip_initial_space:
                continue
            field.append(value)
            at_start = False
    values.append(("".join(field), quoted_field))
    return tuple(values)


def tokenize_record(record: str, spec: "CsvSpec") -> tuple[str | None, ...]:
    """Field values with today's null_sequence semantics (used for header labels)."""
    return tuple(_normalize_field(text, spec) for text, _ in tokenize_record_quoted(record, spec))


def _normalize_field(value: str, spec: "CsvSpec") -> str | None:
    return (
        None
        if spec.null_sequence is not None and value == spec.null_sequence
        else value
    )


def _validate_delimited_spec(spec: "CsvSpec") -> None:
    delimiter, terminator = spec.delimiter, spec.line_terminator
    if not delimiter or not terminator:
        raise ParseError(spec.FORMAT, "delimiter and line terminator must be nonempty")
    for label, char in (("quote", spec.quote_char), ("escape", spec.escape_char)):
        if char is not None and len(char) != 1:
            raise ParseError(spec.FORMAT, f"{label} must be one character or None")
    if spec.quote_char is not None and spec.quote_char == spec.escape_char:
        raise ParseError(spec.FORMAT, "quote and escape must differ")
    if delimiter.startswith(terminator) or terminator.startswith(delimiter):
        raise ParseError(
            spec.FORMAT, "delimiter and terminator must not be equal or prefixes"
        )
    for char in (spec.quote_char, spec.escape_char):
        if char is not None and (char in delimiter or char in terminator):
            raise ParseError(
                spec.FORMAT, "structural tokens must not contain quote or escape"
            )


def encode_field(
    value: object, spec: CsvSpec, *, following: str, first: bool, sole: bool
) -> str:
    """Choose a representation safe against the actual encoded record suffix."""
    if value is None:
        text = spec.null_sequence if spec.null_sequence is not None else ""
    else:
        text = str(value)
        if spec.null_sequence is not None and text == spec.null_sequence:
            raise ValueError("non-null value collides with null marker")
    quote, escape = spec.quote_char, spec.escape_char
    # Comment filtering sees the record after its final terminator is removed.
    # Keep the terminated suffix for structural-token boundary checks below.
    comment_suffix = following[: -len(spec.line_terminator)]
    candidates: list[str] = []
    if quote is not None and (
        quote not in text or spec.double_quote or escape is not None
    ):
        quoted: list[str] = []
        for char in text:
            if escape is not None and char == escape:
                quoted.append(escape * 2)
            elif char == quote:
                if spec.double_quote:
                    quoted.append(quote * 2)
                else:
                    assert escape is not None
                    quoted.append(escape + quote)
            else:
                quoted.append(char)
        candidates.append(quote + "".join(quoted) + quote)

    # A token can begin inside this field and finish in the following suffix.
    combined = text + following
    crosses_token = any(
        combined.startswith(token, index)
        for index in range(len(text))
        for token in (spec.delimiter, spec.line_terminator)
    )
    raw_safe = (
        not crosses_token
        and "\r" not in text
        and "\n" not in text
        and (quote is None or quote not in text)
        and (escape is None or escape not in text)
        and not (spec.skip_initial_space and text.startswith(" "))
    )
    if raw_safe:
        candidates.append(text)

    if escape is not None:
        structural = set(spec.delimiter + spec.line_terminator + "\r\n")
        escaped: list[str] = []
        for char in text:
            protect = (
                char == escape
                or char == quote
                or char in structural
                or (spec.skip_initial_space and char == " ")
            )
            escaped.append(escape + char if protect else char)
        candidate = "".join(escaped)
        candidates.append(candidate)
        # Protect a comment prefix only after retaining the minimally escaped
        # form: the escape itself may also be the configured comment marker.
        if (
            first
            and escaped
            and escaped[0] == text[0]
            and spec.comment_char is not None
            and (candidate + comment_suffix).startswith(spec.comment_char)
        ):
            candidates.append(escape + candidate)

    for candidate in candidates:
        if sole and not candidate:
            continue
        if (
            first
            and spec.comment_char is not None
            and (candidate + comment_suffix).startswith(spec.comment_char)
        ):
            continue
        return candidate
    raise ValueError("field has no safe representation in this record")


def encode_record(row: tuple[object, ...], spec: CsvSpec) -> str:
    """Encode a complete terminated record, working right-to-left for context."""
    if not row:
        raise ValueError("empty record is indistinguishable from a blank line")
    suffix = spec.line_terminator
    for index in reversed(range(len(row))):
        following = (spec.delimiter if index < len(row) - 1 else "") + suffix
        field = encode_field(
            row[index], spec, following=following, first=index == 0, sole=len(row) == 1
        )
        suffix = field + following
    return suffix
