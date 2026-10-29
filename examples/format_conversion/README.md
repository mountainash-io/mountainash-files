# Format conversion

How do I turn CSV into Parquet and NDJSON?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/format_conversion/example.py
```

Expected output:

```text
csv -> parquet: 2 rows preserved
csv -> ndjson: 2 rows preserved
```

Parse the source, then write its table using the destination's format.
The `.ndjson` suffix enables newline-delimited JSON automatically. `copy()`
copies bytes and applies transport transforms; it does not convert formats.
This dataset round-trips through both destinations; other formats may not
preserve every Arrow type or metadata field.

Next: [Parquet append](../parquet_append/).
