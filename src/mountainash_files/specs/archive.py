from __future__ import annotations

import dataclasses

DEFAULT_MAX_DECOMPRESSED_BYTES = 1024**3  # 1 GiB
DEFAULT_MAX_MEMBERS = 10_000


@dataclasses.dataclass(frozen=True)
class GzipCompression:
    """Signals gzip decompression/compression of archive members.

    ``max_decompressed_bytes`` bounds the decompressed output; exceeding it raises
    ``ArchiveLimitError`` during streaming, before the payload is fully allocated.
    """

    max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES


@dataclasses.dataclass(frozen=True)
class ZipArchive:
    """Extract from / create ZIP archives.

    ``max_decompressed_bytes`` bounds the total decompressed size of all extracted
    members (including an ``inner`` gzip layer); ``max_members`` bounds how many
    members are extracted. Exceeding either raises ``ArchiveLimitError``.
    """

    file_pattern: str = "*"
    sort_order: str = "name"
    password: str | None = None
    inner: GzipCompression | None = None
    on_unrecognised: str = "error"
    max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES
    max_members: int = DEFAULT_MAX_MEMBERS
