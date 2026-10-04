"""Parse CSV bytes and serialise the table as newline-delimited JSON."""

from mountainash_files import parse_bytes, serialise_bytes
from mountainash_files.formats.json import JsonSpec

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    result = parse_bytes(SALES, "csv")
    ndjson = JsonSpec(ndjson=True)
    encoded = serialise_bytes(result.data, ndjson)
    decoded = parse_bytes(encoded, ndjson, output="pydata")
    assert decoded.data == [
        {"region": "north", "total": 120},
        {"region": "south", "total": 95},
    ]
    assert len(encoded.splitlines()) == 2
    print(f"{result.format_key}: {result.data.num_rows} rows; NDJSON: 2 lines")
    print(encoded.decode(), end="")


if __name__ == "__main__":
    main()
