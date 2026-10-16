"""Schema discovery over sources: transport routing, missing files, globs, transforms, archives."""
from __future__ import annotations

import gzip
import io
import time
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import (
    FileSourceSpec,
    ParseError,
    SchemaDiscoveryUnsupportedError,
    ZipArchive,
    inspect_schema,
)
from mountainash_files.formats._registry import _reset_registry, register_format

from _range_server import bytes_sent, plain_gets, ranged_gets, serve
from _schema_plugin import TypedSpec, typed_parse


@pytest.fixture(autouse=True)
def fresh_registry():
    _reset_registry()
    yield
    _reset_registry()


def _parquet(n: int = 50_000, **extra) -> bytes:
    columns = {"v": list(range(n)), "s": [str(i) for i in range(n)], **extra}
    sink = io.BytesIO()
    pq.write_table(pa.table(columns), sink)
    return sink.getvalue()


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


# --- Missing sources and capability precedence -------------------------------------------------

def test_missing_supported_source_is_skipped(tmp_path):
    assert inspect_schema(FileSourceSpec(path=str(tmp_path / "x.parquet"), on_missing="skip")) == []


def test_missing_unsupported_source_raises_instead_of_skipping(tmp_path):
    with pytest.raises(SchemaDiscoveryUnsupportedError):
        inspect_schema(FileSourceSpec(path=str(tmp_path / "x.xml"), on_missing="skip"))


def test_invalid_budget_makes_no_request():
    with serve({"a.parquet": _parquet(10)}) as (base, log):
        with pytest.raises(ValueError):
            inspect_schema(FileSourceSpec(path=f"{base}/a.parquet"), infer_schema_rows=0)
    assert log == []


# --- Transport routing --------------------------------------------------------------------------

def test_http_parquet_fetches_the_footer_only():
    raw = _parquet()
    with serve({"a.parquet": raw}) as (base, log):
        (result,) = inspect_schema(FileSourceSpec(path=f"{base}/a.parquet"))
    assert result.schema.names == ["v", "s"] and result.basis == "metadata"
    assert plain_gets(log) == 0 and ranged_gets(log) >= 1
    assert bytes_sent(log) < len(raw) // 2


def test_server_without_ranges_falls_back_to_whole_object():
    with serve({"a.parquet": _parquet(100)}, ranges=False) as (base, log):
        (result,) = inspect_schema(FileSourceSpec(path=f"{base}/a.parquet"))
    assert result.schema.names == ["v", "s"] and plain_gets(log) >= 1


HANDLES: list = []


def _head_inspector(fail: bool):
    def inspect(data, spec, *, infer_schema_rows=None):
        HANDLES.append(data)
        head = data[:10] if isinstance(data, bytes) else data.read(10)
        if fail:
            raise RuntimeError("inspector failed")
        return pa.schema([("n", pa.int64())]), "bounded" if len(head) == 10 else "full"
    return inspect


@pytest.mark.parametrize("fail", [False, True])
def test_bounded_http_prefix_closes_the_stream(fail):
    HANDLES.clear()
    register_format(TypedSpec, typed_parse, schema_inspector=_head_inspector(fail), schema_access="sequential")
    payload = b"x" * 40_000_000   # well above loopback socket buffering (a few MB)
    with serve({"a.typed": payload}) as (base, log):
        if fail:
            with pytest.raises(RuntimeError):
                inspect_schema(FileSourceSpec(path=f"{base}/a.typed"))
        else:
            (result,) = inspect_schema(FileSourceSpec(path=f"{base}/a.typed"))
            assert result.basis == "bounded"
        assert not isinstance(HANDLES[0], bytes) and HANDLES[0].closed
        deadline = time.monotonic() + 5
        while not log and time.monotonic() < deadline:   # the server logs once its write loop ends
            time.sleep(0.01)
    assert log and bytes_sent(log) < len(payload) // 2


def test_schema_access_callable_must_return_a_mode(tmp_path):
    register_format(TypedSpec, typed_parse, schema_inspector=_head_inspector(False),
                    schema_access=lambda spec, n: "bogus")
    path = tmp_path / "a.typed"
    path.write_bytes(b"int64:1")
    with pytest.raises(ValueError):
        inspect_schema(FileSourceSpec(path=str(path)))


# --- Paths, globs, transforms, archives -----------------------------------------------------------

def test_template_params_and_overwrite_are_observed_fresh(tmp_path):
    path = tmp_path / "day1.parquet"
    path.write_bytes(_parquet(10))
    source = FileSourceSpec(path=str(tmp_path / "{day}.parquet"))
    assert inspect_schema(source, params={"day": "day1"})[0].schema.names == ["v", "s"]
    path.write_bytes(_parquet(10, extra=list(range(10))))
    assert inspect_schema(source, params={"day": "day1"})[0].schema.names == ["v", "s", "extra"]


def test_glob_yields_one_result_per_file_in_name_order(tmp_path):
    (tmp_path / "b.parquet").write_bytes(_parquet(5, only_b=list(range(5))))
    (tmp_path / "a.parquet").write_bytes(_parquet(5))
    results = inspect_schema(FileSourceSpec(path=str(tmp_path), glob="*.parquet"))
    assert [r.schema.names for r in results] == [["v", "s"], ["v", "s", "only_b"]]


def test_no_glob_match_is_empty(tmp_path):
    assert inspect_schema(FileSourceSpec(path=str(tmp_path), glob="*.parquet")) == []


def test_gzip_transform_uses_whole_object_bytes(tmp_path):
    path = tmp_path / "a.parquet.gz"
    path.write_bytes(gzip.compress(_parquet(10)))
    (result,) = inspect_schema(FileSourceSpec(path=str(path)))
    assert result.schema.names == ["v", "s"]


def test_zip_members_each_yield_a_result_and_skips_are_recorded(tmp_path):
    path = tmp_path / "a.zip"
    path.write_bytes(_zip({"one.parquet": _parquet(5), "two.parquet": _parquet(5, t=list(range(5))),
                           "notes.unknown": b"?"}))
    results = inspect_schema(FileSourceSpec(path=str(path), archive=ZipArchive(on_unrecognised="skip")))
    assert [r.schema.names for r in results] == [["v", "s"], ["v", "s", "t"]]
    assert all(r.skipped_members == ("notes.unknown",) for r in results)


def test_recognised_member_without_inspector_is_not_skipped(tmp_path):
    path = tmp_path / "a.zip"
    path.write_bytes(_zip({"one.parquet": _parquet(5), "doc.xml": b"<a/>"}))
    with pytest.raises(SchemaDiscoveryUnsupportedError):
        inspect_schema(FileSourceSpec(path=str(path), archive=ZipArchive(on_unrecognised="skip")))


def test_failing_later_member_raises_instead_of_partial_results(tmp_path):
    path = tmp_path / "a.zip"
    path.write_bytes(_zip({"a.parquet": _parquet(5), "b.parquet": b"broken"}))
    with pytest.raises(ParseError):
        inspect_schema(FileSourceSpec(path=str(path), archive=ZipArchive()))
