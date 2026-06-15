from __future__ import annotations

import dataclasses
import typing as t

if t.TYPE_CHECKING:
    from mountainash_files.formats._types import FormatSpec
    from mountainash_files.specs.archive import GzipCompression, ZipArchive
    from mountainash_transport import Pipeline


@dataclasses.dataclass(frozen=True)
class FileSpec:
    """A file somewhere with a format and auth."""

    path: str
    format: str | FormatSpec | None = None
    auth_profile: str | None = None
    archive: ZipArchive | GzipCompression | None = None
    transforms: Pipeline | None = None
