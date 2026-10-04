# Parquet append

How do I append rows and handle incompatible schemas?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/parquet_append/example.py
```

Expected output:

```text
parquet: 2 rows after append
incompatible schema rejected; destination unchanged
```

`write_disposition="append"` accepts Arrow tables or record data and creates a
missing destination. Existing and incoming ordered column names and Arrow types
must match. The recipe catches `AppendSchemaMismatchError` and confirms that
rejection occurs before the destination changes.

Append reads and rewrites the entire table in memory. Use a single writer with
full read/write access; append is not an atomic transaction. Compression requires
an explicit symmetric pipeline. See the [full contract](../../docs/advanced-usage.md#write-modes).

Next: [globs and templates](../globs_and_templates/).
