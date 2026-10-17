# Globs and templates

How do I select multiple files and skip missing inputs?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/globs_and_templates/example.py
```

Expected output:

```text
glob: 2 files; regions: north, south
missing report: 0 results
```

Operations expand `{region}` from `params`. A source's `path` is the base
directory when `glob` is supplied; matching files are read in sorted order.
Results remain separate until the application combines them.

An unmatched glob returns `[]`. `on_missing="skip"` also returns `[]` for a
missing file, but does not hide format, parse or permission errors. Globs use
the same path-style rule (`*` within a directory, `**` across) on every backend
that supports object listing.

Next: [ZIP archives](../zip_archives/).
