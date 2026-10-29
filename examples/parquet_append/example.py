"""Append a matching Parquet row and reject an incompatible column type."""

import tempfile
from pathlib import Path

import pyarrow as pa

from mountainash_files import (
    AppendSchemaMismatchError,
    FileSinkSpec,
    FileSourceSpec,
    parse,
    write,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.parquet")
        write(FileSinkSpec(path=path), pa.table({"region": ["north"], "total": [120]}))
        append = FileSinkSpec(path=path, write_disposition="append")
        write(append, {"region": "south", "total": 95})
        before = Path(path).read_bytes()

        try:
            write(append, {"region": "west", "total": "unknown"})
        except AppendSchemaMismatchError as exc:
            assert exc.path == path
        else:
            raise AssertionError("Expected the incompatible total type to be rejected")

        assert Path(path).read_bytes() == before
        result, = parse(FileSourceSpec(path=path), output="pydata")
        assert result.data == [
            {"region": "north", "total": 120},
            {"region": "south", "total": 95},
        ]
        print("parquet: 2 rows after append")
        print("incompatible schema rejected; destination unchanged")


if __name__ == "__main__":
    main()
