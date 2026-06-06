from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class GzipCompression:
    """Signals gzip decompression/compression of archive members."""

    pass


@dataclasses.dataclass(frozen=True)
class ZipArchive:
    """Extract from / create ZIP archives."""

    file_pattern: str = "*"
    sort_order: str = "name"
    password: str | None = None
    inner: GzipCompression | None = None
