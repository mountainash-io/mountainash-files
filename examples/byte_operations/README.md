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
The current implementation buffers the complete file in memory, so reading
chunks from it does not provide bounded-memory storage access.

Next: [named profiles](../named_profiles/).
