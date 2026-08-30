from __future__ import annotations

from pathlib import Path

from mountainash_resource_provider import DetectedResourceFormat, ResourceRequest

from mountainash_files.provider import FileResourceProvider


def request(path: Path) -> ResourceRequest:
    return ResourceRequest(
        name="records",
        locator=str(path),
        detected_format=DetectedResourceFormat(
            canonical_format="csv",
            dialect_family="delimited",
            provider_format_key="csv",
            detection_source="suffix",
        ),
        encoding="utf-8",
        dialect={},
        dialect_context={},
        schema=None,
        metadata={},
    )


def test_planning_does_not_read_or_resolve_settings(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    path.write_text("id\n1\n")
    provider = FileResourceProvider.default()
    assert provider.plan(request(path)).payload["locator"] == str(path)


def test_read_arrow_reads_local_resource_at_execution_time(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    path.write_text("id\n1\n")
    provider = FileResourceProvider.default()
    assert provider.read_arrow(provider.plan(request(path))).table.to_pylist() == [{"id": 1}]


def test_structured_read_resolves_deferred_row_shape(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    path.write_text('[{"id": 1}]')
    provider = FileResourceProvider.default()
    structured_request = ResourceRequest(
        name="records",
        locator=str(path),
        detected_format=DetectedResourceFormat("json", "structured", "json", "suffix"),
        encoding="utf-8",
        dialect={"header": True, "item_type": "object"},
        dialect_context={},
        schema=None,
        metadata={},
    )
    result = provider.read_arrow(provider.plan(structured_request))
    assert result.resolved_context == {"structured_row_shape": "object"}
