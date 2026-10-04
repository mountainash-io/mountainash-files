"""Public typing contract, checked and executed outside the source checkout."""

import dataclasses
import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, BinaryIO, assert_type

import pyarrow as pa

from mountainash_files import (
    FileSourceSpec,
    FormatSpec,
    ParseResult,
    parse,
    parse_bytes,
    serialise_bytes,
    stream,
)
from mountainash_files.formats.csv import CsvSpec
from mountainash_files.formats.json import JsonSpec, json_parse


@dataclasses.dataclass(frozen=True)
class CustomCsv(CsvSpec):
    label: str = "example"


spec = assert_type(CustomCsv.from_options({"label": "custom"}), CustomCsv)
assert spec.label == "custom"
result = assert_type(parse_bytes(b"x\n1\n", CsvSpec()), ParseResult)
# Registry plugins can return non-tabular payloads; the wrapper must stay typed.
assert_type(result.data, Any)
assert isinstance(result.data, pa.Table)
assert result.data.to_pylist() == [{"x": 1}]
assert_type(result.spec, FormatSpec)
wire = assert_type(serialise_bytes(pa.table({"x": [1]}), CsvSpec()), bytes)
assert list(csv.reader(io.StringIO(wire.decode()))) == [["x"], ["1"]]
assert_type(FileSourceSpec(path="rows.csv").path, str)
scalars = assert_type(json_parse(b"[1, 2]", JsonSpec()), pa.Table | list[object])
assert scalars == [1, 2]

with TemporaryDirectory() as directory:
    path = Path(directory) / "rows.csv"
    path.write_bytes(wire)
    source = FileSourceSpec(path=str(path))
    parsed = assert_type(parse(source), list[ParseResult])
    assert parsed[0].data.to_pylist() == [{"x": 1}]
    with stream(source) as reader:
        assert_type(reader, BinaryIO)
        assert reader.read() == wire
    assert reader.closed

if TYPE_CHECKING:
    # --warn-unused-ignores makes these required rejections, including Any drift.
    parse_bytes(123, CsvSpec())  # type: ignore[arg-type]
    parse_bytes(b"x", CsvSpec(), output="invalid")  # type: ignore[arg-type]
    wrong: str = serialise_bytes(pa.table({"x": [1]}), CsvSpec())  # type: ignore[assignment]
    wrong_label: int = spec.label  # type: ignore[assignment]
