# Byte operations

How do I copy and read bytes without parsing?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/byte_operations/example.py
```

Expected output:

```text
copy: 32 decoded bytes preserved
stream: header read, 2 data lines remain
```

Raw `bytes` passed to `write()` bypass serialisation while still using transport
transforms. `copy()` decodes the source and writes its bytes; a sink pipeline can
re-encode them. It does not parse, convert formats or append tables.

`stream()` yields a binary stream in a context manager and closes it on exit.
The example reads the 13-byte header before consuming the remaining data. Files
delegates directly to transport without first draining the stream. Transport's
backend or transform may still buffer internally (GPG currently does).
Seek only when `reader.seekable()` is true; seekability is not guaranteed for
every source. Opening and subsequent reads can fail, so consume within the context.

Use `FileSourceSpec(path=source, infer=False)` to stream or copy the original
compressed bytes instead. The default infers gzip; explicit `transforms` override
that default. Combining `infer=True` with `transforms` raises `ValueError`.

Next: [named profiles](../named_profiles/).
