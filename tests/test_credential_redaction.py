"""W8 design sections 2 and 5: no sentinel reaches any files error surface."""
from __future__ import annotations

import io
import logging
import traceback
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import (
    AppendSchemaMismatchError,
    FileSinkSpec,
    FileSourceSpec,
    ParseError,
    UnknownFormatError,
    WriteError,
    ZipArchive,
    inspect_schema,
    parse,
    write,
)
from mountainash_files._safe_location import safe_detail
from tests._range_server import serve

SENTINELS = ("SENTU", "SENTP", "SENTQ", "SENTF")


def _surfaces(exc: BaseException) -> list[str]:
    """Every text a caller can reach from *exc*, including hidden chain members."""
    out, seen, stack = [], set(), [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        out += [str(current), repr(current), repr(current.args), repr(vars(current))]
        stack += [current.__cause__, current.__context__]
    out.append("".join(traceback.format_exception(exc)))
    return out


def assert_no_sentinel(exc: BaseException, logs: list[str] = ()) -> None:
    leaked = [t for t in [*_surfaces(exc), *logs] if any(s in t for s in SENTINELS)]
    assert not leaked, leaked


LOCATIONS = {
    "userinfo": "https://SENTU:SENTP@host.example/d/x.xyz",
    "at-in-password": "https://SENTU:pa@SENTP@host.example/x.xyz",
    "query-and-fragment": "sftp://SENTU:SENTP@host.example/x.xyz?token=SENTQ#SENTF",
    "network-path": "//SENTU:SENTP@host.example/x.xyz",
    "single-slash": "https:/SENTU:SENTP@host.example/x.xyz",
    "scheme-less": "SENTU:SENTP@host.example/x.xyz?token=SENTQ",
    "leading-whitespace": " \thttps://SENTU:SENTP@host.example/x.xyz",
}

OPERATIONS = {
    "parse": lambda path: parse(FileSourceSpec(path=path)),
    "inspect_schema": lambda path: inspect_schema(FileSourceSpec(path=path)),
    "write": lambda path: write(FileSinkSpec(path=path), pa.table({"a": [1]})),
}


@pytest.mark.parametrize("location", LOCATIONS.values(), ids=LOCATIONS.keys())
@pytest.mark.parametrize("operation", OPERATIONS.values(), ids=OPERATIONS.keys())
def test_unknown_format_error_hides_credentials(operation, location):
    with pytest.raises(UnknownFormatError) as info:
        operation(location)
    assert_no_sentinel(info.value)


def _zip(member: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, b"x")
    return buffer.getvalue()


@pytest.mark.parametrize("on_unrecognised", ["error", "skip"])
def test_archive_parse_errors_hide_credentials(on_unrecognised, caplog):
    with serve({"a.zip?sig=SENTQ": _zip("member.xyz")}) as (base, _):
        url = base.replace("http://", "http://SENTU:SENTP@") + "/a.zip?sig=SENTQ#SENTF"
        with caplog.at_level(logging.WARNING), pytest.raises(ParseError) as info:
            parse(FileSourceSpec(path=url, archive=ZipArchive(on_unrecognised=on_unrecognised)))
    assert_no_sentinel(info.value, caplog.messages)
    assert "127.0.0.1" in str(info.value)


def test_append_schema_mismatch_hides_credentials():
    existing = io.BytesIO()
    pq.write_table(pa.table({"a": [1]}), existing)
    with serve({"m.parquet?sig=SENTQ": existing.getvalue()}) as (base, _):
        url = base.replace("http://", "http://SENTU:SENTP@") + "/m.parquet?sig=SENTQ"
        sink = FileSinkSpec(path=url, format="parquet", write_disposition="append")
        with pytest.raises(AppendSchemaMismatchError) as info:
            write(sink, pa.table({"b": ["x"]}))
    assert_no_sentinel(info.value)


def test_append_combine_failure_shows_type_only_and_no_chain(monkeypatch, tmp_path):
    path = str(tmp_path / "m.parquet")
    write(FileSinkSpec(path=path), pa.table({"a": [1]}))

    def fail(_tables):
        raise pa.ArrowInvalid("SENTQ leaked from pyarrow")

    monkeypatch.setattr(pa, "concat_tables", fail)
    with pytest.raises(WriteError) as info:
        write(FileSinkSpec(path=path, write_disposition="append"), pa.table({"a": [2]}))
    assert "ArrowInvalid" in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert_no_sentinel(info.value)


def test_unsafe_member_resolution_error_is_not_shown_or_chained(monkeypatch):
    import mountainash_files._operations as operations

    def fail(**_kwargs):
        raise ValueError("SENTQ from a plugin")

    monkeypatch.setattr(operations, "resolve_format", fail)
    with serve({"a.zip": _zip("member.csv")}) as (base, _), pytest.raises(ParseError) as info:
        parse(FileSourceSpec(path=f"{base}/a.zip", archive=ZipArchive()))
    assert "ValueError" in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert_no_sentinel(info.value)


def test_oserror_detail_keeps_errno_and_strerror_only():
    exc = FileNotFoundError(2, "No such file or directory", "/SENTU:SENTP@h/x.csv")
    assert safe_detail(exc) == "[Errno 2] No such file or directory"


def test_other_native_detail_is_type_name_only():
    assert safe_detail(RuntimeError("SENTQ")) == "RuntimeError"
