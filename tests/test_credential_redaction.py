"""W8: no credential reaches a files error surface (message, repr, attributes, chain)."""
from __future__ import annotations

import io
import traceback
import zipfile
from pathlib import PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import (
    AppendSchemaMismatchError,
    FileSinkSpec,
    FileSourceSpec,
    ParseError,
    UnknownFormatError,
    ZipArchive,
    inspect_schema,
    parse,
    write,
)
from tests._range_server import serve

SENTINELS = ("SENTU", "SENTP", "SENTQ")


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


def assert_no_sentinel(exc: BaseException) -> None:
    leaked = [text for text in _surfaces(exc) if any(s in text for s in SENTINELS)]
    assert not leaked, leaked


LOCATIONS = {
    "userinfo": "https://SENTU:SENTP@host.example/d/x.xyz",
    "s3-userinfo": "s3://SENTU:SENTP@bucket/x.xyz",
    "at-in-password": "https://SENTU:pa@SENTP@host.example/x.xyz",
    "query-token": "https://host.example/x.xyz?X-Amz-Signature=SENTQ&X-Amz-Credential=SENTQ",
    "userinfo-and-query": "sftp://SENTU:SENTP@host.example/x.xyz?token=SENTQ#frag",
    "scheme-less-userinfo": "SENTU:SENTP@host.example/x.xyz",
    "scheme-less-userinfo-and-query": "SENTU:SENTP@host.example/x.xyz?token=SENTQ",
    "network-path-userinfo": "//SENTU:SENTP@host.example/x.xyz",
    "fragment-token": "https://host.example/x.xyz#access_token=SENTQ",
    "single-slash": "https:/SENTU:SENTP@host.example/x.xyz",
    "opaque-scheme": "s3:SENTU:SENTP@bucket/x.xyz",
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


@pytest.mark.parametrize(
    ("location", "shown"),
    [
        ("sftp://SENTU:SENTP@host.example:2222/x.xyz?token=SENTQ#frag", "sftp://host.example:2222/x.xyz"),
        ("https://SENTU:pa@SENTP@[::1]:8443/d/x.xyz", "https://[::1]:8443/d/x.xyz"),
        ("//SENTU:SENTP@host.example/x.xyz", "//host.example/x.xyz"),
        ("https://host.example/a@b/x.xyz", "https://host.example/a@b/x.xyz"),
        ("SENTU:SENTP@host.example/x.xyz", "***"),
        ("https:/SENTU:SENTP@host.example/x.xyz", "***"),
        ("a:SENTP@host/x.xyz", "***"),
    ],
)
def test_remote_locations_show_only_scheme_host_and_path(location, shown):
    assert UnknownFormatError(path=location, known_suffixes=(".csv",)).path == shown


@pytest.mark.parametrize(
    "path",
    ["data/x.xyz", "/srv/team@corp/x.xyz", "C:/data/x.xyz", "C:\\data\\x.xyz", "relative/a:b@c/x.xyz"],
)
def test_local_paths_are_shown_unchanged(path):
    assert UnknownFormatError(path=path, known_suffixes=(".csv",)).path == path


def test_pathlike_location_is_reported_as_text():
    err = UnknownFormatError(path=PurePosixPath("/data/x.xyz"), known_suffixes=(".csv",))
    assert err.path == "/data/x.xyz"


def _zip(member: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, b"x")
    return buffer.getvalue()


@pytest.mark.parametrize("on_unrecognised", ["error", "skip"])
def test_archive_parse_errors_hide_credentials(on_unrecognised):
    with serve({"a.zip?sig=SENTQ": _zip("member.xyz")}) as (base, _):
        url = base.replace("http://", "http://SENTU:SENTP@") + "/a.zip?sig=SENTQ"
        with pytest.raises(ParseError) as info:
            parse(FileSourceSpec(path=url, archive=ZipArchive(on_unrecognised=on_unrecognised)))
    assert_no_sentinel(info.value)


def test_append_schema_mismatch_hides_credentials():
    existing = io.BytesIO()
    pq.write_table(pa.table({"a": [1]}), existing)
    with serve({"m.parquet?sig=SENTQ": existing.getvalue()}) as (base, _):
        url = base.replace("http://", "http://SENTU:SENTP@") + "/m.parquet?sig=SENTQ"
        sink = FileSinkSpec(path=url, format="parquet", write_disposition="append")
        with pytest.raises(AppendSchemaMismatchError) as info:
            write(sink, pa.table({"b": ["x"]}))
    assert_no_sentinel(info.value)
