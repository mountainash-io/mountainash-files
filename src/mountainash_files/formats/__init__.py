"""Built-in format parsers. Importing this module triggers registration."""

import mountainash_files.formats.csv  # noqa: F401
import mountainash_files.formats.tsv  # noqa: F401
import mountainash_files.formats.json  # noqa: F401
import mountainash_files.formats.parquet  # noqa: F401
import mountainash_files.formats.xlsx  # noqa: F401
import mountainash_files.formats.xml  # noqa: F401

from mountainash_files.formats._registry import _discover_entrypoint_formats

_discover_entrypoint_formats()
