"""Write templated paths, select a glob and skip an absent report."""

import tempfile
from pathlib import Path

import pyarrow as pa

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

SALES = [{"region": "north", "total": 120}, {"region": "south", "total": 95}]


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        template = str(Path(root) / "{region}.csv")
        for row in SALES:
            write(
                FileSinkSpec(path=template), pa.Table.from_pylist([row]),
                params={"region": row["region"]},
            )

        results = parse(FileSourceSpec(path=root, glob="*.csv"), output="pydata")
        rows = [row for result in results for row in result.data]
        assert rows == SALES
        missing = parse(
            FileSourceSpec(path=template, on_missing="skip"),
            params={"region": "west"},
        )
        assert missing == []
        assert parse(FileSourceSpec(path=root, glob="*.parquet")) == []
        print(f"glob: {len(results)} files; regions: {', '.join(row['region'] for row in rows)}")
        print("missing report: 0 results")


if __name__ == "__main__":
    main()
