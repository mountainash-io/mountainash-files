from pathlib import Path

import pytest

from mountainash_files._glob import resolve_glob

FIXTURES = Path(__file__).parent / "fixtures"
GLOB_DIR = FIXTURES / "glob_dir"


@pytest.fixture
def tree(tmp_path):
    for rel in ["a.csv", ".hidden.csv", "b.txt", "sub/c.csv", "sub/deep/d.csv", "other/e.csv"]:
        path = tmp_path / "base" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n1\n")
    return tmp_path / "base"


def names(paths, base):
    return [str(Path(p).relative_to(base)) for p in paths]


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


class TestPathStyleRule:
    def test_star_stays_within_one_directory(self, tree):
        assert names(resolve_glob(str(tree), "*.csv"), tree) == [".hidden.csv", "a.csv"]

    def test_segment_pattern_selects_one_directory(self, tree):
        assert names(resolve_glob(str(tree), "sub/*.csv"), tree) == ["sub/c.csv"]

    def test_double_star_matches_zero_or_more_directories(self, tree):
        assert names(resolve_glob(str(tree), "**/*.csv"), tree) == [
            ".hidden.csv", "a.csv", "other/e.csv", "sub/c.csv", "sub/deep/d.csv",
        ]
        assert names(resolve_glob(str(tree), "sub/**/*.csv"), tree) == ["sub/c.csv", "sub/deep/d.csv"]

    def test_double_star_alone_matches_every_file(self, tree):
        assert len(resolve_glob(str(tree), "**")) == 6

    def test_question_mark_and_class_stay_within_a_segment(self, tree):
        assert names(resolve_glob(str(tree), "?.csv"), tree) == ["a.csv"]
        assert names(resolve_glob(str(tree), "[as]*/*.csv"), tree) == ["sub/c.csv"]

    def test_trailing_slash_base_is_the_same_base(self, tree):
        assert resolve_glob(str(tree) + "/", "**/*.csv") == resolve_glob(str(tree), "**/*.csv")

    def test_relative_base_returns_readable_paths(self, tree, monkeypatch):
        monkeypatch.chdir(tree.parent)
        paths = resolve_glob("base", "sub/*.csv")
        assert len(paths) == 1 and Path(paths[0]).read_text() == "x\n1\n"

    def test_missing_base_is_empty(self, tmp_path):
        assert resolve_glob(str(tmp_path / "missing"), "**/*.csv") == []
