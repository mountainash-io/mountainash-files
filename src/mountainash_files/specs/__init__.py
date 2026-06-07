from mountainash_files.specs.archive import GzipCompression, ZipArchive
from mountainash_files.specs.base import FileSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.source import FileSourceSpec

__all__ = [
    "FileSpec",
    "FileSinkSpec",
    "FileSourceSpec",
    "GzipCompression",
    "ZipArchive",
]
