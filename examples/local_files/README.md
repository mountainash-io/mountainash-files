# Local files

How do I write a table and read Arrow or Python records?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/local_files/example.py
```

Expected output:

```text
csv: 2 rows as Arrow
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': 95}]
```

`write()` serialises the Arrow table according to the destination suffix.
`parse()` returns a list even for one file; unpacking `result,` expects exactly
one result. `output="pydata"` requests Python records instead of the default
Arrow table. Both results retain the format key and resolved format spec.

Next: [in-memory data](../in_memory/).
