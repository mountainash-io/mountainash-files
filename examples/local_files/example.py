"""Write a sales table and read it as Arrow and Python records."""

import tempfile
from pathlib import Path

import pyarrow as pa

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

SALES = [{"region": "north", "total": 120}, {"region": "south", "total": 95}]


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv")
        write(FileSinkSpec(path=path), pa.Table.from_pylist(SALES))

        result, = parse(FileSourceSpec(path=path))
        records, = parse(FileSourceSpec(path=path), output="pydata")
        assert isinstance(result.data, pa.Table)
        assert result.format_key == "csv" and result.data.to_pylist() == SALES
        assert records.data == SALES
        print(f"{result.format_key}: {result.data.num_rows} rows as Arrow")
        print(records.data)


if __name__ == "__main__":
    main()
