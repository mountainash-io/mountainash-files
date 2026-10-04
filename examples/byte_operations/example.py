"""Copy compressed input to plain bytes and read it through a buffered stream."""

import tempfile
from pathlib import Path

from mountainash_transport import Gzip, Pipeline

from mountainash_files import FileSinkSpec, FileSourceSpec, copy, stream, write

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        source = str(Path(root) / "sales.csv.gz")
        destination = str(Path(root) / "sales-copy.csv")
        write(FileSinkSpec(path=source, transforms=Pipeline(Gzip())), SALES)
        copy(FileSourceSpec(path=source), FileSinkSpec(path=destination))
        assert Path(destination).read_bytes() == SALES

        with stream(FileSourceSpec(path=source)) as buffer:
            assert buffer.readline() == b"region,total\n"
            remaining = buffer.read()
            assert remaining == b"north,120\nsouth,95\n"
        assert buffer.closed
        print(f"copy: {len(SALES)} decoded bytes preserved")
        print(f"stream: header read, {len(remaining.splitlines())} data lines remain")


if __name__ == "__main__":
    main()
