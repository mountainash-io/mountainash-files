from __future__ import annotations

from mountainash_files.formats._registry import iter_provider_formats


def test_registry_derives_complete_provider_descriptors() -> None:
    descriptors = {descriptor.canonical_format: descriptor for descriptor in iter_provider_formats()}

    assert descriptors["csv"].provider_format_key == "csv"
    assert descriptors["tsv"].aliases == frozenset({"tab"})
    assert descriptors["ndjson"].provider_format_key == "json"
    assert descriptors["ndjson"].suffixes == frozenset({".ndjson", ".jsonl"})
    assert descriptors["geojson"].dialect_family == "structured"
    assert descriptors["xlsx"].dialect_family == "spreadsheet"
    assert descriptors["parquet"].dialect_family is None
    assert descriptors["xml"].mediatypes == frozenset({"application/xml", "text/xml"})
    assert {descriptor.provider_format_key for descriptor in descriptors.values()} <= {
        "csv",
        "tsv",
        "json",
        "xlsx",
        "parquet",
        "xml",
    }
