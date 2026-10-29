"""mountainash-files: Composable file operations with format detection and parsing."""

from mountainash_files._exceptions import (
    AppendSchemaMismatchError,
    MissingDependencyError,
    WriteError,
)
from mountainash_files._operations import (
    copy,
    inspect_schema,
    inspect_schema_bytes,
    parse,
    parse_bytes,
    serialise_bytes,
    stream,
    write,
)
from mountainash_files.formats._exceptions import (
    FormatConflictError,
    FormatError,
    FormatResolutionError,
    ParseError,
    SchemaDiscoveryUnsupportedError,
    UnknownFormatError,
)
from mountainash_files.formats._protocols import FormatParser, FormatSchemaInspector, FormatSerialiser
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec, ParseResult, SchemaResult
from mountainash_files.specs.archive import GzipCompression, ZipArchive
from mountainash_files.specs.base import FileSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.source import FileSourceSpec

# Trigger built-in format registration
import mountainash_files.formats  # noqa: F401

__all__ = [
    "copy",
    "parse",
    "parse_bytes",
    "inspect_schema",
    "inspect_schema_bytes",
    "serialise_bytes",
    "stream",
    "write",
    "register_format",
    "FileSpec",
    "FileSinkSpec",
    "FileSourceSpec",
    "FormatSpec",
    "ParseResult",
    "SchemaResult",
    "GzipCompression",
    "ZipArchive",
    "FormatError",
    "FormatParser",
    "FormatSchemaInspector",
    "FormatSerialiser",
    "UnknownFormatError",
    "ParseError",
    "FormatConflictError",
    "FormatResolutionError",
    "SchemaDiscoveryUnsupportedError",
    "WriteError",
    "AppendSchemaMismatchError",
    "MissingDependencyError",
]
