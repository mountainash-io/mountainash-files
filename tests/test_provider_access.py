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

    plan = provider.plan(request(path))

    assert plan.payload["locator"] == str(path)


def test_read_arrow_reads_local_resource_at_execution_time(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    path.write_text("id\n1\n")
    provider = FileResourceProvider.default()

    result = provider.read_arrow(provider.plan(request(path)))

    assert result.table.to_pylist() == [{"id": 1}]
