from __future__ import annotations

import dataclasses
import typing as t

from mountainash_files.specs.base import FileSpec

if t.TYPE_CHECKING:
    from mountainash_transport import GPG, Gzip


@dataclasses.dataclass(frozen=True)
class FileSourceSpec(FileSpec):
    """Read-side: where to get data from."""

    glob: str | None = None
    on_missing: t.Literal["skip", "raise"] = "raise"
    infer: bool | None = None
    gpg: GPG | None = None
    gzip: Gzip | None = None
