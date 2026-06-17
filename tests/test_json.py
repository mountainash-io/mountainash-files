from pathlib import Path

import pytest

from mountainash_files.formats.json import JsonSpec, json_parse
from mountainash_files.formats._exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


class TestJsonSpec:
    def test_defaults(self):
        spec = JsonSpec()
        assert spec.FORMAT == "json"
        assert spec.records_path is None
        assert spec.ndjson is False

    def test_suffixes(self):
        assert ".json" in JsonSpec.SUFFIXES
        assert ".ndjson" in JsonSpec.SUFFIXES
        assert ".jsonl" in JsonSpec.SUFFIXES


class TestJsonParse:
    def test_single_object(self):
        data = b'{"name": "Alice", "age": 30}'
        result = json_parse(data, JsonSpec())
        assert isinstance(result, dict)
        assert result["name"] == "Alice"

    def test_array_of_objects(self):
        data = b'[{"a": 1}, {"a": 2}]'
        result = json_parse(data, JsonSpec())
        assert isinstance(result, list)
        assert len(result) == 2

    def test_records_path(self):
        data = (FIXTURES / "sample_records.json").read_bytes()
        result = json_parse(data, JsonSpec(records_path="data.users"))
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_records_path_missing_key(self):
        data = b'{"a": 1}'
        with pytest.raises(ParseError, match="json"):
            json_parse(data, JsonSpec(records_path="b.c"))

    def test_records_path_missing_key_empty_on_missing(self):
        # Opt-in: an absent records collection yields [] instead of raising.
        data = b"{}"
        result = json_parse(data, JsonSpec(records_path="dataPoints", empty_on_missing=True))
        assert result == []

    def test_records_path_missing_nested_key_empty_on_missing(self):
        data = b'{"a": 1}'
        result = json_parse(data, JsonSpec(records_path="b.c", empty_on_missing=True))
        assert result == []

    def test_records_path_present_empty_list_unaffected(self):
        # empty_on_missing does not change behavior when the key IS present.
        data = b'{"dataPoints": []}'
        result = json_parse(data, JsonSpec(records_path="dataPoints", empty_on_missing=True))
        assert result == []

    def test_ndjson(self):
        data = (FIXTURES / "sample.ndjson").read_bytes()
        result = json_parse(data, JsonSpec(ndjson=True))
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["name"] == "Alice"

    def test_empty_raises(self):
        with pytest.raises(ParseError, match="json"):
            json_parse(b"", JsonSpec())

    def test_malformed_raises(self):
        with pytest.raises(ParseError, match="json"):
            json_parse(b"{invalid json", JsonSpec())

    def test_from_stream(self):
        import io
        data = io.BytesIO(b'{"x": 1}')
        result = json_parse(data, JsonSpec())
        assert result == {"x": 1}
