"""Convert CSV into Parquet and NDJSON through the parsed Arrow table."""

import tempfile
from pathlib import Path

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        source = Path(root) / "sales.csv"
        source.write_bytes(SALES)
        original, = parse(FileSourceSpec(path=str(source)))
        for suffix in ("parquet", "ndjson"):
            destination = str(Path(root) / f"sales.{suffix}")
            write(FileSinkSpec(path=destination), original.data)
            converted, = parse(FileSourceSpec(path=destination))
            assert converted.data.to_pylist() == original.data.to_pylist()
            if suffix == "ndjson":
                assert len(Path(destination).read_bytes().splitlines()) == 2
            print(f"csv -> {suffix}: {converted.data.num_rows} rows preserved")


if __name__ == "__main__":
    main()
