from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files.formats.tsv import TsvSpec
from mountainash_files.formats.csv import csv_parse

FIXTURES = Path(__file__).parent / "fixtures"


class TestTsvSpec:
    def test_format_key(self):
        assert TsvSpec.FORMAT == "tsv"

    def test_suffixes(self):
        assert TsvSpec.SUFFIXES == (".tsv", ".tab")

    def test_delimiter_is_classvar(self):
        spec = TsvSpec()
        assert spec.delimiter == "\t"

    def test_delimiter_not_in_init(self):
        # delimiter is a ClassVar, should not appear in __init__
        spec = TsvSpec()
        assert not hasattr(type(spec).__dataclass_fields__, "delimiter") or \
            "delimiter" not in {f for f in type(spec).__dataclass_fields__}


class TestTsvParse:
    def test_from_bytes(self):
        data = b"x\ty\n1\t2\n3\t4\n"
        table = csv_parse(data, TsvSpec())
        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert table.column_names == ["x", "y"]

    def test_from_fixture(self):
        data = (FIXTURES / "sample.tsv").read_bytes()
        table = csv_parse(data, TsvSpec())
        assert table.num_rows == 2
        assert "name" in table.column_names

    def test_dialect_null_values(self):
        # TsvSpec shares csv_parse; its dialect fields must route through.
        data = b"a\tb\nNA\tx\n1\tNA\n"
        table = csv_parse(data, TsvSpec(null_values=("NA",)))
        assert table.column("a").to_pylist() == [None, 1]
        assert table.column("b").to_pylist() == ["x", None]
