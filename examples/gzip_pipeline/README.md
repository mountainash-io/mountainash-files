# Gzip pipeline

How do I compress writes and infer decompression on read?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/gzip_pipeline/example.py
```

Expected output:

```text
sales.csv.gz: gzip bytes on disk
inferred and explicit decoding: 2 matching rows
```

The explicit `Pipeline(Gzip())` compresses the serialised CSV on write. A `.gz`
suffix alone does not compress output. Normal reads infer decompression when
there is no explicit pipeline; the remaining `.csv` suffix selects the parser.
Supplying the same pipeline on read gives the same records.

Parquet append needs an explicit symmetric pipeline for both its read and write
steps; it does not infer transforms from suffixes.

Next: [byte operations](../byte_operations/).
