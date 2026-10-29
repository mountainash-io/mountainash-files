from __future__ import annotations

import dataclasses

DEFAULT_MAX_DECOMPRESSED_BYTES = 1024**3  # 1 GiB
DEFAULT_MAX_MEMBERS = 10_000


def require_positive_limits(spec: object, *names: str) -> None:
    """Reject decompression limits that are not positive ints (bool excluded)."""
    for name in names:
        value = getattr(spec, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive int")


@dataclasses.dataclass(frozen=True)
class GzipCompression:
    """Signals gzip decompression/compression of archive members.

    ``max_decompressed_bytes`` bounds the decompressed output; exceeding it raises
    ``ArchiveLimitError`` during streaming, before the payload is fully allocated.
    """

    max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES

    def __post_init__(self) -> None:
        require_positive_limits(self, "max_decompressed_bytes")


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

    def __post_init__(self) -> None:
        require_positive_limits(self, "max_decompressed_bytes", "max_members")
