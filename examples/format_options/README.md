# Format options

How do I override a suffix and configure CSV parsing?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/format_options/example.py
```

Expected output:

```text
explicit format: csv; columns: ['total']
[{'total': 120}, {'total': 95}]
```

An explicit `CsvSpec` selects CSV despite the `.dat` suffix. Here it sets a
semicolon delimiter, removes comment records and selects the `total` column.
Format specs are immutable dataclasses. `to_options()` omits default values;
`from_options()` restores tuple fields after a JSON round trip.

See the [reference](../../docs/advanced-usage.md#format-options) for other specs
and CSV null/quoting semantics.

Next: [format conversion](../format_conversion/).
