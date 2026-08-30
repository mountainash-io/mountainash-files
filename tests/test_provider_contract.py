from __future__ import annotations

from mountainash_resource_provider import (
    DetectedResourceFormat,
    DialectFieldDisposition,
    ResourceRequest,
)
from mountainash_resource_provider.testing import run_provider_contract

from mountainash_files.provider import FileResourceProvider


def request() -> ResourceRequest:
    return ResourceRequest(
        name="records",
        locator="records.csv",
        detected_format=DetectedResourceFormat(
            canonical_format="csv",
            dialect_family="delimited",
            provider_format_key="csv",
            detection_source="suffix",
        ),
        encoding="utf-8",
        dialect={"header": True},
        dialect_context={},
        schema=None,
        metadata={},
    )


def test_file_provider_plan_uses_registry_metadata_without_runtime_state() -> None:
    provider = FileResourceProvider.default()

    plan = provider.plan(request())

    assert plan.provider_key == "file"
    assert plan.dialect_fields == {"header": DialectFieldDisposition.CONSUMED}
    assert plan.payload["parser_key"] == "csv"
    assert "access" not in plan.payload


def test_file_provider_satisfies_neutral_contract() -> None:
    results = run_provider_contract(lambda: FileResourceProvider.default(), [request()])

    assert all(result.error is None for result in results if result.check != "arrow")
