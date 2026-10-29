from pathlib import Path

import pyarrow as pa

from mountainash_files import FileSourceSpec, parse


def test_parse_csv_to_relation():
    import mountainash as ma

    fixture = Path(__file__).parents[2] / "tests" / "fixtures" / "sample.csv"
    results = parse(FileSourceSpec(path=str(fixture)))
    assert len(results) == 1
    assert isinstance(results[0].data, pa.Table)
    rel = ma.relation(results[0].data)
    assert rel is not None
