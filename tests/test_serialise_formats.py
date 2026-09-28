import io
import json

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

from mountainash_files.formats.csv import CsvSpec, csv_serialise
from mountainash_files.formats.json import JsonSpec, json_serialise
from mountainash_files.formats.parquet import ParquetSpec, parquet_serialise
from mountainash_files.formats.xml import XmlSpec, xml_serialise


class TestCsvSerialise:
    def test_arrow_table(self):
        table = pa.table({"x": [1, 2], "y": [3, 4]})
        result = csv_serialise(table, CsvSpec())
        assert isinstance(result, bytes)
        assert b"x" in result
        assert b"1" in result

    def test_roundtrip(self):
        table = pa.table({"name": ["Alice", "Bob"], "age": [30, 25]})
        data = csv_serialise(table, CsvSpec())
        restored = pcsv.read_csv(io.BytesIO(data))
        assert restored.num_rows == 2
        assert restored.column_names == ["name", "age"]

    def test_custom_delimiter(self):
        table = pa.table({"a": [1], "b": [2]})
        data = csv_serialise(table, CsvSpec(delimiter=";"))
        assert b";" in data


class TestJsonSerialise:
    def test_dict(self):
        data = {"name": "Alice", "age": 30}
        result = json_serialise(data, JsonSpec())
        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert parsed == data

    def test_list(self):
        data = [{"a": 1}, {"a": 2}]
        result = json_serialise(data, JsonSpec())
        parsed = json.loads(result)
        assert parsed == data

    def test_ndjson(self):
        data = [{"a": 1}, {"a": 2}]
        result = json_serialise(data, JsonSpec(ndjson=True))
        lines = [json.loads(line) for line in result.splitlines() if line.strip()]
        assert lines == data

    def test_arrow_table_to_json(self):
        table = pa.table({"x": [1, 2]})
        result = json_serialise(table, JsonSpec())
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2


class TestParquetSerialise:
    def test_arrow_table(self):
        table = pa.table({"x": [1, 2], "y": [3, 4]})
        result = parquet_serialise(table, ParquetSpec())
        assert isinstance(result, bytes)
        restored = pq.read_table(io.BytesIO(result))
        assert restored.num_rows == 2

    def test_roundtrip(self):
        table = pa.table({"name": ["Alice"], "age": [30]})
        data = parquet_serialise(table, ParquetSpec())
        restored = pq.read_table(io.BytesIO(data))
        assert restored.column("name")[0].as_py() == "Alice"


class TestXmlSerialise:
    def test_stdlib_element(self):
        import xml.etree.ElementTree as ET
        root = ET.Element("root")
        child = ET.SubElement(root, "item")
        child.text = "hello"
        result = xml_serialise(root, XmlSpec())
        assert isinstance(result, bytes)
        assert b"hello" in result
