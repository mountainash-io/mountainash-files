"""Compress on write and infer gzip decoding when parsing the result."""

import gzip
import tempfile
from pathlib import Path

import pyarrow as pa
from mountainash_transport import Gzip, Pipeline

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, parse_bytes, write

SALES = [{"region": "north", "total": 120}, {"region": "south", "total": 95}]


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv.gz")
        pipeline = Pipeline(Gzip())
        write(
            FileSinkSpec(path=path, transforms=pipeline),
            pa.Table.from_pylist(SALES),
        )
        compressed = Path(path).read_bytes()
        assert compressed.startswith(b"\x1f\x8b")
        decoded = parse_bytes(gzip.decompress(compressed), "csv", output="pydata")
        assert decoded.data == SALES

        inferred, = parse(FileSourceSpec(path=path), output="pydata")
        explicit, = parse(FileSourceSpec(path=path, transforms=pipeline), output="pydata")
        assert inferred.data == explicit.data == SALES
        print("sales.csv.gz: gzip bytes on disk")
        print("inferred and explicit decoding: 2 matching rows")


if __name__ == "__main__":
    main()
