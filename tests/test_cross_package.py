"""Cross-package integration tests between mountainash-files and sibling packages."""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa

FIXTURES = Path(__file__).parent / "fixtures"


class TestTransformSuffixesSync:
    def test_utils_files_suffixes_are_subset(self):
        from mountainash_files.formats._registry import TRANSFORM_SUFFIXES
        from mountainash_transport.storage.path_helpers.suffixes import SUFFIX_TRANSFORMS

        utils_suffixes = set(SUFFIX_TRANSFORMS.keys())
        assert utils_suffixes.issubset(TRANSFORM_SUFFIXES), (
            f"mountainash-files TRANSFORM_SUFFIXES missing: {utils_suffixes - TRANSFORM_SUFFIXES}"
        )


class TestParseToRelation:
    def test_parse_csv_to_relation(self):
        import mountainash as ma
        from mountainash_files import parse, FileSourceSpec

        results = parse(FileSourceSpec(path=str(FIXTURES / "sample.csv")))
        assert len(results) == 1
        assert isinstance(results[0].data, pa.Table)

        rel = ma.relation(results[0].data)
        assert rel is not None
