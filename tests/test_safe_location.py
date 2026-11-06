"""W8 design section 1: what an error shows of a location (rendering table)."""
from __future__ import annotations

from pathlib import PurePosixPath

import pyarrow as pa
import pytest

from mountainash_files import AppendSchemaMismatchError, UnknownFormatError

# Shared across packages (spec section 5.1): keep identical to the other packages' copies.
RENDERING = [
    # scheme:// — scheme, host, port, path only
    ("https://SENTU:SENTP@h:8443/a/x.csv?sig=SENTQ#SENTF", "https://h:8443/a/x.csv"),
    ("https://SENTU:pa@SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@[::1]:8443/d/x.csv", "https://[::1]:8443/d/x.csv"),
    ("https://host/a@b/x.csv", "https://host/a@b/x.csv"),
    ("https://host/x.csv#access_token=SENTF", "https://host/x.csv"),
    ("https://host/x.csv?SENTQ", "https://host/x.csv"),
    ("https://host/x.csv#f?tok=SENTQ", "https://host/x.csv"),
    ("https://host", "https://host"),
    ("s3://bucket/x.csv", "s3://bucket/x.csv"),
    ("file:///tmp/x.csv", "file:///tmp/x.csv"),
    ("HTTPS://SENTU:SENTP@host/x.csv", "HTTPS://host/x.csv"),
    ("postgresql+psycopg://SENTU:SENTP@db/name", "postgresql+psycopg://db/name"),
    # //network path
    ("//SENTU:SENTP@host/x.csv", "//host/x.csv"),
    # whitespace / control characters, as urllib reads them
    (" \thttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@ho\nst/x.csv", "https://host/x.csv"),
    # other scheme strings
    ("https:/SENTU:SENTP@host/x.csv", "***"),
    ("s3:SENTU:SENTP@bucket/x.csv", "***"),
    ("SENTU:SENTP@host/x.csv", "***"),
    ("a:SENTP@host/x.csv", "***"),
    # local paths
    ("/data/x.csv", "/data/x.csv"),
    ("data/x.csv", "data/x.csv"),
    ("/srv/team@corp/x.csv", "/srv/team@corp/x.csv"),
    ("relative/a:b@c/x.csv", "relative/a:b@c/x.csv"),
    ("C:/d/x.csv", "C:/d/x.csv"),
    ("C:\\d\\x.csv", "C:\\d\\x.csv"),
]


@pytest.mark.parametrize(("location", "shown"), RENDERING)
def test_unknown_format_error_shows_safe_location(location, shown):
    err = UnknownFormatError(path=location, known_suffixes=(".csv",))
    assert err.path == shown
    assert f"path={shown!r}" in str(err)


@pytest.mark.parametrize(("location", "shown"), RENDERING)
def test_append_schema_mismatch_shows_safe_location(location, shown):
    schema = pa.schema([("a", pa.int64())])
    err = AppendSchemaMismatchError(location, schema, schema)
    assert err.path == shown
    assert f"for {shown!r}" in str(err)


def test_pathlike_location_is_shown_as_text():
    err = UnknownFormatError(path=PurePosixPath("/data/x.csv"), known_suffixes=(".csv",))
    assert err.path == "/data/x.csv"


def test_explicit_format_key_has_no_path():
    assert UnknownFormatError(path=None, known_suffixes=(".csv",)).path is None
