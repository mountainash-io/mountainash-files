from __future__ import annotations

import fnmatch
import gzip
import io
import zipfile
from collections.abc import Iterator

from mountainash_files.specs.archive import GzipCompression, ZipArchive


class ArchiveExtractionError(Exception):
    """Failed to extract from archive."""


class ArchiveEmptyMatchError(ArchiveExtractionError):
    """No members matched the file pattern."""


def unpack_archive(
    data: bytes,
    archive: ZipArchive | GzipCompression,
) -> Iterator[tuple[str, bytes]]:
    """Yield (member_name, member_bytes) from an archive."""
    if isinstance(archive, GzipCompression):
        yield from _unpack_gzip(data)
    elif isinstance(archive, ZipArchive):
        yield from _unpack_zip(data, archive)
    else:
        raise ArchiveExtractionError(f"Unknown archive type: {type(archive)}")


def _unpack_gzip(data: bytes) -> Iterator[tuple[str, bytes]]:
    if len(data) == 0:
        raise ArchiveExtractionError("Empty gzip input")
    try:
        decompressed = gzip.decompress(data)
    except Exception as exc:
        raise ArchiveExtractionError(f"Gzip decompression failed: {exc}") from exc
    yield ("", decompressed)


def _unpack_zip(data: bytes, archive: ZipArchive) -> Iterator[tuple[str, bytes]]:
    if len(data) == 0:
        raise ArchiveExtractionError("Empty ZIP input")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        raise ArchiveExtractionError(f"Invalid ZIP file: {exc}") from exc

    with zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]

        if archive.file_pattern != "*":
            names = [n for n in names if fnmatch.fnmatch(n, archive.file_pattern)]

        if not names:
            raise ArchiveEmptyMatchError(
                f"No members matched pattern {archive.file_pattern!r}"
            )

        if archive.sort_order == "name":
            names.sort()

        pwd = None
        if archive.password is not None:
            if isinstance(archive.password, str):
                pwd = archive.password.encode("utf-8")
            elif hasattr(archive.password, "get_secret_value"):
                pwd = archive.password.get_secret_value().encode("utf-8")
            elif hasattr(archive.password, "resolve"):
                pwd = archive.password.resolve().encode("utf-8")

        for name in names:
            member_data = zf.read(name, pwd=pwd)
            if archive.inner is not None and isinstance(archive.inner, GzipCompression):
                member_data = gzip.decompress(member_data)
            yield (name, member_data)
