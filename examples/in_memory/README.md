# In-memory data

How do I parse and serialise buffers without a file?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/in_memory/example.py
```

Expected output:

```text
csv: 2 rows; NDJSON: 2 lines
{"region": "north", "total": 120}
{"region": "south", "total": 95}
```

`parse_bytes()` takes bytes or a binary file-like object and returns one
`ParseResult`. It requires an explicit format because there is no filename.
`serialise_bytes()` returns bytes without storage access. Use
`JsonSpec(ndjson=True)` for NDJSON buffers; `ndjson` is a suffix convention,
not a registered format key.

Next: [format options](../format_options/).
