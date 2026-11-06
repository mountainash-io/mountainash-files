"""W8 design sections 2 and 5: no sentinel reaches any files error surface."""
from __future__ import annotations

import io
import logging
import traceback
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from mountainash_transport.location import LocationPolicy

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
    "parse": lambda path, policy: parse(FileSourceSpec(path=path, policy=policy)),
    "inspect_schema": lambda path, policy: inspect_schema(FileSourceSpec(path=path, policy=policy)),
    "write": lambda path, policy: write(FileSinkSpec(path=path, policy=policy), pa.table({"a": [1]})),
}

POLICIES = {
    "no-policy": None,
    "policy": LocationPolicy(allowed_remote={"http": frozenset({"127.0.0.1"})}),
}


def files_logs(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name.startswith("mountainash_files")]


@pytest.mark.parametrize("policy", POLICIES.values(), ids=POLICIES.keys())
@pytest.mark.parametrize("location", LOCATIONS.values(), ids=LOCATIONS.keys())
@pytest.mark.parametrize("operation", OPERATIONS.values(), ids=OPERATIONS.keys())
def test_unknown_format_error_hides_credentials(operation, location, policy):
    with pytest.raises(UnknownFormatError) as info:
        operation(location, policy)
    assert_no_sentinel(info.value)


def _zip(member: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, b"x")
    return buffer.getvalue()


def _credential_url(base: str, name: str) -> str:
    return base.replace("http://", "http://SENTU:SENTP@") + f"/{name}?sig=SENTQ#SENTF"


@pytest.mark.parametrize("policy", POLICIES.values(), ids=POLICIES.keys())
@pytest.mark.parametrize("on_unrecognised", ["error", "skip"])
def test_archive_parse_errors_hide_credentials(on_unrecognised, policy, caplog):
    with serve({"a.zip?sig=SENTQ": _zip("member.xyz")}) as (base, _):
        url = _credential_url(base, "a.zip")
        source = FileSourceSpec(path=url, archive=ZipArchive(on_unrecognised=on_unrecognised), policy=policy)
        with caplog.at_level(logging.DEBUG), pytest.raises(ParseError) as info:
            parse(source)
    assert_no_sentinel(info.value, files_logs(caplog))
    assert "127.0.0.1" in str(info.value)


@pytest.mark.parametrize("policy", POLICIES.values(), ids=POLICIES.keys())
def test_append_schema_mismatch_hides_credentials(policy):
    existing = io.BytesIO()
    pq.write_table(pa.table({"a": [1]}), existing)
    with serve({"m.parquet?sig=SENTQ": existing.getvalue()}) as (base, _):
        sink = FileSinkSpec(
            path=_credential_url(base, "m.parquet"), format="parquet",
            write_disposition="append", policy=policy,
        )
        with pytest.raises(AppendSchemaMismatchError) as info:
            write(sink, pa.table({"b": ["x"]}))
    assert_no_sentinel(info.value)


def test_append_combine_failure_hides_location_and_native_text(monkeypatch):
    existing = io.BytesIO()
    pq.write_table(pa.table({"a": [1]}), existing)

    def fail(_tables):
        raise pa.ArrowInvalid("SENTQ leaked from pyarrow")

    monkeypatch.setattr(pa, "concat_tables", fail)
    with serve({"m.parquet?sig=SENTQ": existing.getvalue()}) as (base, _):
        sink = FileSinkSpec(path=_credential_url(base, "m.parquet"), format="parquet", write_disposition="append")
        with pytest.raises(WriteError) as info:
            write(sink, pa.table({"a": [2]}))
    assert "ArrowInvalid" in str(info.value)
    assert "127.0.0.1" in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None
    assert_no_sentinel(info.value)


def _parse_archive_with_member_failure(monkeypatch, make_failure, on_unrecognised, caplog):
    import mountainash_files._operations as operations

    def fail(**_kwargs):
        raise make_failure()

    monkeypatch.setattr(operations, "resolve_format", fail)
    archive = ZipArchive(on_unrecognised=on_unrecognised)
    with (
        serve({"a.zip": _zip("member.csv")}) as (base, _),
        caplog.at_level(logging.DEBUG),
        pytest.raises(ParseError) as info,
    ):
        parse(FileSourceSpec(path=f"{base}/a.zip", archive=archive))
    return info.value


@pytest.mark.parametrize("on_unrecognised", ["error", "skip"])
@pytest.mark.parametrize(
    "make_failure",
    [lambda: ValueError("SENTQ from a plugin"), lambda: ParseError("csv", "SENTQ from a plugin")],
    ids=["native", "content-parse-error"],
)
def test_unsafe_member_resolution_error_is_not_shown_or_chained(monkeypatch, caplog, make_failure, on_unrecognised):
    error = _parse_archive_with_member_failure(monkeypatch, make_failure, on_unrecognised, caplog)
    shown = str(error) if on_unrecognised == "error" else " ".join(files_logs(caplog))
    assert type(make_failure()).__name__ in shown
    assert error.__cause__ is None and error.__context__ is None
    assert_no_sentinel(error, files_logs(caplog))


def test_oserror_member_failure_is_chained_without_filename(monkeypatch, caplog):
    def make_failure():
        return FileNotFoundError(2, "No such file or directory", "https://SENTU:SENTP@h/x?SENTQ")

    error = _parse_archive_with_member_failure(monkeypatch, make_failure, "error", caplog)
    assert "[Errno 2] No such file or directory" in str(error)
    assert type(error.__cause__) is FileNotFoundError
    assert error.__cause__.filename is None
    assert_no_sentinel(error)


class _PickyOSError(OSError):
    """An OSError subclass whose constructor rejects the two-argument form."""

    def __init__(self, *args):
        if len(args) == 2:
            raise ValueError("SENTQ from the constructor")
        super().__init__(*args)


def test_oserror_subclass_that_cannot_be_rebuilt_is_chained_as_plain_oserror(monkeypatch, caplog):
    def make_failure():
        return _PickyOSError(2, "No such file or directory", "https://SENTU:SENTP@h/x?SENTQ")

    error = _parse_archive_with_member_failure(monkeypatch, make_failure, "error", caplog)
    assert isinstance(error.__cause__, OSError) and error.__cause__.errno == 2
    assert error.__cause__.filename is None
    assert_no_sentinel(error)


def test_oserror_without_errno_is_not_chained(monkeypatch, caplog):
    def make_failure():
        return OSError("SENTQ message")

    error = _parse_archive_with_member_failure(monkeypatch, make_failure, "error", caplog)
    assert "OSError" in str(error)
    assert error.__cause__ is None and error.__context__ is None
    assert_no_sentinel(error)


def test_oserror_detail_keeps_errno_and_strerror_only():
    exc = FileNotFoundError(2, "No such file or directory", "/SENTU:SENTP@h/x.csv")
    assert safe_detail(exc) == "[Errno 2] No such file or directory"


@pytest.mark.parametrize(
    "exc",
    [RuntimeError("SENTQ"), ParseError("csv", "SENTQ content"), WriteError("SENTQ")],
    ids=["native", "parse-error", "write-error"],
)
def test_other_detail_is_type_name_only(exc):
    assert safe_detail(exc) == type(exc).__name__
