"""Select CSV members from a ZIP archive and parse each separately."""

import tempfile
import zipfile
from pathlib import Path

from mountainash_files import FileSourceSpec, ZipArchive, parse


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "sales.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("south.csv", "region,total\nsouth,95\n")
            archive.writestr("north.csv", "region,total\nnorth,120\n")
            archive.writestr("notes.txt", "Sales report for two regions.")

        results = parse(
            FileSourceSpec(path=str(path), archive=ZipArchive(file_pattern="*.csv")),
            output="pydata",
        )
        rows = [row for result in results for row in result.data]
        assert rows == [
            {"region": "north", "total": 120},
            {"region": "south", "total": 95},
        ]
        assert all(result.format_key == "csv" for result in results)
        print(f"zip: {len(results)} CSV members in name order")
        print(rows)


if __name__ == "__main__":
    main()
