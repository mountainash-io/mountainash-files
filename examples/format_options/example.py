"""Read semicolon-separated data using an explicit, portable CSV spec."""

import json
import tempfile
from pathlib import Path

from mountainash_files import FileSourceSpec, parse
from mountainash_files.formats.csv import CsvSpec

SALES = b"# sales report\nregion;total\nnorth;120\nsouth;95\n"


def main() -> None:
    spec = CsvSpec(delimiter=";", comment_char="#", columns=("total",))
    options = json.loads(json.dumps(spec.to_options()))
    restored = CsvSpec.from_options(options)
    assert restored == spec

    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "sales.dat"
        path.write_bytes(SALES)
        result, = parse(FileSourceSpec(path=str(path), format=restored))
        assert result.format_key == "csv"
        assert result.data.to_pylist() == [{"total": 120}, {"total": 95}]
        print(f"explicit format: {result.format_key}; columns: {result.data.column_names}")
        print(result.data.to_pylist())


if __name__ == "__main__":
    main()
