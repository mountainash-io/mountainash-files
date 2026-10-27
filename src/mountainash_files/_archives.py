from __future__ import annotations

import fnmatch
import gzip
import io
import zipfile
from collections.abc import Callable, Iterator

from mountainash_files.specs.archive import GzipCompression, ZipArchive

_CHUNK = 64 * 1024


class ArchiveExtractionError(Exception):
    """Failed to extract from archive."""


class ArchiveEmptyMatchError(ArchiveExtractionError):
    """No members matched the file pattern."""


class ArchiveLimitError(ArchiveExtractionError):
    """Archive exceeded a decompression limit (size or member count)."""


class _Budget:
    """Running decompressed-byte count shared across members."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def read_all(self, read: Callable[[int], bytes], label: str) -> bytes:
        out = bytearray()
        while chunk := read(min(_CHUNK, self.limit - self.used + 1)):
            self.used += len(chunk)
            if self.used > self.limit:
                raise ArchiveLimitError(
                    f"{label}: decompressed size exceeds max_decompressed_bytes="
                    f"{self.limit}; raise the limit on the archive spec if trusted"
                )
            out += chunk
        return bytes(out)


def unpack_archive(
    data: bytes,
    archive: ZipArchive | GzipCompression,
) -> Iterator[tuple[str, bytes]]:
    """Yield (member_name, member_bytes) from an archive."""
    if isinstance(archive, GzipCompression):
        yield from _unpack_gzip(data, archive)
    elif isinstance(archive, ZipArchive):
        yield from _unpack_zip(data, archive)
    else:
        raise ArchiveExtractionError(f"Unknown archive type: {type(archive)}")


def _unpack_gzip(data: bytes, archive: GzipCompression) -> Iterator[tuple[str, bytes]]:
    if len(data) == 0:
        raise ArchiveExtractionError("Empty gzip input")
    budget = _Budget(archive.max_decompressed_bytes)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            decompressed = budget.read_all(stream.read, "gzip")
    except ArchiveLimitError:
        raise
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

        if len(names) > archive.max_members:
            raise ArchiveLimitError(
                f"zip: {len(names)} members exceeds max_members={archive.max_members}; "
                "scope with file_pattern or raise the limit if trusted"
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

        budget = _Budget(archive.max_decompressed_bytes)
        for name in names:
            with zf.open(name, pwd=pwd) as member:
                if isinstance(archive.inner, GzipCompression):
                    with gzip.GzipFile(fileobj=member) as inner:
                        member_data = budget.read_all(inner.read, f"zip member {name!r}")
                else:
                    member_data = budget.read_all(member.read, f"zip member {name!r}")
            yield (name, member_data)
