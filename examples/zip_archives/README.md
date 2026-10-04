# ZIP archives

How do I parse selected members of an archive?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/zip_archives/example.py
```

Expected output:

```text
zip: 2 CSV members in name order
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': 95}]
```

The standard library creates the input archive. Files' `ZipArchive` selects
members for reading; it does not create archives on write. `file_pattern="*.csv"`
excludes the notes file and default name sorting puts north before south,
regardless of insertion order. Each member's suffix selects its parser.

Unrecognised selected members fail by default. Use a precise pattern or opt into
`on_unrecognised="skip"`; skipped names are recorded in `ParseResult.skipped_members`.
See [archive semantics](../../docs/advanced-usage.md#globs-archives-and-missing-files).

Next: [gzip pipeline](../gzip_pipeline/).
