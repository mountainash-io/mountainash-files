from __future__ import annotations

import fnmatch
import gzip
import io
import struct
import zipfile
import zlib
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

    def __init__(self, limit: int, raise_hint: str = "the limit on the archive spec") -> None:
        self.limit = limit
        self.used = 0
        self._hint = raise_hint

    def _chunks(self, read: Callable[[int], bytes], label: str) -> Iterator[bytes]:
        while chunk := read(min(_CHUNK, self.limit - self.used + 1)):
            self.used += len(chunk)
            if self.used > self.limit:
                raise ArchiveLimitError(
                    f"{label}: decompressed size exceeds max_decompressed_bytes="
                    f"{self.limit}; raise {self._hint} if trusted"
                )
            yield chunk

    def read_all(self, read: Callable[[int], bytes], label: str) -> bytes:
        out = bytearray()
        for chunk in self._chunks(read, label):
            out += chunk
        return bytes(out)

    def drain(self, read: Callable[[int], bytes], label: str) -> None:
        """Count the bytes *read* yields against the budget and discard them."""
        for _ in self._chunks(read, label):
            pass


_LOCAL_HEADER = struct.Struct("<4s5H3L2H")
_LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"


def _inflating_reader(raw: memoryview, info: zipfile.ZipInfo, start: int) -> Callable[[int], bytes]:
    """``read(n)`` over the member data at ``raw[start:]``, yielding at most *n* bytes.

    A deflated member is inflated until its own compressed stream ends, so neither the
    declared uncompressed size nor the declared compressed size can be forged to hide
    inflation. A stored member is its declared length, which the input itself bounds.
    """
    position = start
    if info.compress_type == zipfile.ZIP_STORED:
        end = min(start + info.compress_size, len(raw))

        def read_stored(n: int) -> bytes:
            nonlocal position
            chunk = bytes(raw[position : min(position + n, end)])
            position += len(chunk)
            return chunk

        return read_stored

    inflater = zlib.decompressobj(-zlib.MAX_WBITS)

    def read_deflated(n: int) -> bytes:
        nonlocal position
        while True:
            if inflater.unconsumed_tail:
                out = inflater.decompress(inflater.unconsumed_tail, n)
            elif inflater.eof:
                return b""
            elif position >= len(raw):
                raise ArchiveExtractionError("zip member is truncated")
            else:
                feed = bytes(raw[position : position + _CHUNK])
                position += len(feed)
                out = inflater.decompress(feed, n)
            if out or inflater.eof:
                return out

    return read_deflated


_END_RECORD = struct.Struct("<4s4H2LH")
_END_RECORD_SIGNATURE = b"PK\x05\x06"
_ZIP64_LOCATOR = struct.Struct("<4sLQL")
_ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
_ZIP64_END_RECORD = struct.Struct("<4sQ2H2L4Q")
_ZIP64_END_RECORD_SIGNATURE = b"PK\x06\x06"


def _declared_entries(data: bytes) -> int | None:
    """Entry count the container declares, after requiring one unambiguous directory.

    Returns None only if *data* holds no end record signature anywhere, which no zip reader
    can open. Python's zipfile walks the central directory by its declared byte size and
    looks for the zip64 locator whenever one is present, while other readers (calamine's zip
    crate) may walk it by the declared entry count, read the zip64 record only when the
    classic fields are sentinels, search the whole input for the end record, or pick another
    end record if the data holds more than one. A container where those could disagree would
    let members hide from this check, so anything but a plain, single, exactly-sized
    directory with a signature-consistent end is refused. The search spans the whole input
    (a signature outside zipfile's 64 KiB window is refused, not skipped).
    """
    pos = data.rfind(_END_RECORD_SIGNATURE)
    if pos < 0:
        return None
    if pos + _END_RECORD.size > len(data):
        raise ArchiveExtractionError("zip: truncated end record")
    _, disk, cd_disk, on_disk, total, size, offset, comment = _END_RECORD.unpack_from(data, pos)
    if pos + _END_RECORD.size + comment != len(data):
        raise ArchiveExtractionError("zip: data after the end record")
    end = pos
    loc = pos - _ZIP64_LOCATOR.size
    has_locator = loc >= 0 and data[loc : loc + 4] == _ZIP64_LOCATOR_SIGNATURE
    sentinel = total == 0xFFFF or 0xFFFFFFFF in (size, offset)
    if has_locator != sentinel:
        raise ArchiveExtractionError("zip: zip64 locator and end record fields disagree")
    if sentinel:
        end = _ZIP64_LOCATOR.unpack_from(data, loc)[2]
        if end + _ZIP64_END_RECORD.size > len(data) or data[end : end + 4] != _ZIP64_END_RECORD_SIGNATURE:
            raise ArchiveExtractionError("zip: zip64 end record is malformed")
        classic = (disk, cd_disk, on_disk, total, size, offset)
        _, _, _, _, disk, cd_disk, on_disk, total, size, offset = _ZIP64_END_RECORD.unpack_from(data, end)
        # a reader may take each field from either record: a classic field that is not the
        # sentinel must say what the zip64 record says
        for shown, real, sentinel_value in zip(
            classic,
            (disk, cd_disk, on_disk, total, size, offset),
            (0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF),
            strict=True,
        ):
            if shown not in (real, sentinel_value):
                raise ArchiveExtractionError("zip: zip64 and classic end records disagree")
    if disk or cd_disk or on_disk != total:
        raise ArchiveExtractionError("zip: multi-disk archives are not supported")
    if offset + size != end:
        raise ArchiveExtractionError("zip: central directory does not end at the end record")
    zip64 = 1 if sentinel else 0
    for signature, expected in (
        (_END_RECORD_SIGNATURE, 1),
        (_ZIP64_END_RECORD_SIGNATURE, zip64),
        (_ZIP64_LOCATOR_SIGNATURE, zip64),
    ):
        if data.count(signature, offset) != expected:
            raise ArchiveExtractionError("zip: more than one end record")
    return total


def check_zip_container(
    data: bytes,
    *,
    max_decompressed_bytes: int,
    max_members: int,
    size_hint: str,
    members_hint: str,
) -> bool:
    """Bound a zip container before a third-party reader sees it.

    Returns False without checking anything if *data* has no zip end record (the caller's
    reader then fails as it always did). Otherwise counts every directory entry against
    *max_members*, then inflates every member in chunks, discarding the output, against a
    single running *max_decompressed_bytes* budget. Raises ``ArchiveLimitError`` over either
    limit (its message names *size_hint* / *members_hint*, the setting to raise) and
    ``ArchiveExtractionError`` if the container is malformed, has an ambiguous directory
    (see ``_declared_entries``), or holds a member this check cannot bound: encrypted, or
    compressed with a method other than stored/deflate.
    """
    declared = _declared_entries(data)
    if declared is None:
        return False
    if declared > max_members:
        raise ArchiveLimitError(
            f"zip: {declared} members exceeds max_members={max_members}; "
            f"raise {members_hint} if trusted"
        )
    view = memoryview(data)
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        raise ArchiveExtractionError(f"Invalid ZIP file: {exc}") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) != declared:
            raise ArchiveExtractionError(
                f"zip: central directory holds {len(infos)} entries but declares {declared}"
            )
        budget = _Budget(max_decompressed_bytes, size_hint)
        for info in infos:
            label = f"zip member {info.filename!r}"
            if info.flag_bits & 0x1:
                raise ArchiveExtractionError(f"{label}: encrypted members are not supported")
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ArchiveExtractionError(
                    f"{label}: unsupported compression method {info.compress_type}"
                )
            if not 0 <= info.header_offset <= len(view) - _LOCAL_HEADER.size:
                raise ArchiveExtractionError(f"{label}: bad local file header")
            header = _LOCAL_HEADER.unpack_from(view, info.header_offset)
            if header[0] != _LOCAL_HEADER_SIGNATURE:
                raise ArchiveExtractionError(f"{label}: bad local file header")
            start = info.header_offset + _LOCAL_HEADER.size + header[-2] + header[-1]
            try:
                budget.drain(_inflating_reader(view, info, start), label)
            except zlib.error as exc:
                raise ArchiveExtractionError(f"{label}: corrupt compressed data: {exc}") from exc
    return True


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
