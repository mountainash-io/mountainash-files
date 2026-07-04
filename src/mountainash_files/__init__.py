"""mountainash-files: Composable file operations with format detection and parsing."""

from mountainash_files._exceptions import MissingDependencyError, WriteError
from mountainash_files._operations import copy, parse, parse_bytes, serialise_bytes, stream, write
from mountainash_files.formats._exceptions import (
    FormatConflictError,
    FormatError,
    ParseError,
    UnknownFormatError,
)
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec, ParseResult
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
    "serialise_bytes",
    "stream",
    "write",
    "register_format",
    "FileSpec",
    "FileSinkSpec",
    "FileSourceSpec",
    "FormatSpec",
    "ParseResult",
    "GzipCompression",
    "ZipArchive",
    "FormatError",
    "UnknownFormatError",
    "ParseError",
    "FormatConflictError",
    "WriteError",
    "MissingDependencyError",
]
