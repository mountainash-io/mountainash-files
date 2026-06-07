from pathlib import Path

import pytest

from mountainash_files._glob import resolve_glob

FIXTURES = Path(__file__).parent / "fixtures"
GLOB_DIR = FIXTURES / "glob_dir"


class TestLocalGlob:
    def test_star_csv(self):
        paths = resolve_glob(str(GLOB_DIR), "*.csv")
        assert len(paths) == 2
        assert all(p.endswith(".csv") for p in paths)

    def test_star_all(self):
        paths = resolve_glob(str(GLOB_DIR), "*")
        assert len(paths) >= 3

    def test_recursive(self):
        paths = resolve_glob(str(GLOB_DIR), "**/*.csv")
        assert len(paths) == 3  # 2 top-level + 1 nested

    def test_no_match_returns_empty(self):
        paths = resolve_glob(str(GLOB_DIR), "*.xyz")
        assert paths == []

    def test_sorted_by_name(self):
        paths = resolve_glob(str(GLOB_DIR), "*.csv")
        assert paths == sorted(paths)

    def test_specific_pattern(self):
        paths = resolve_glob(str(GLOB_DIR), "data_*.csv")
        assert len(paths) == 2
