from __future__ import annotations

import pytest

from mountainash_files.formats.csv import csv_parse
from mountainash_files.formats.tsv import TsvSpec


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(False, " leading"), (True, "leading")],
)
def test_tsv_skip_initial_space_is_discriminating(enabled: bool, expected: str) -> None:
    table = csv_parse(b"left\tright\na\t leading\n", TsvSpec(skip_initial_space=enabled))
    assert table.to_pylist() == [{"left": "a", "right": expected}]


def test_tsv_uses_complete_delimited_behavior() -> None:
    table = csv_parse(
        b"group\tvalue\na\t\"two\nlines\"\n",
        TsvSpec(),
    )
    assert table.to_pylist() == [{"group": "a", "value": "two\nlines"}]
