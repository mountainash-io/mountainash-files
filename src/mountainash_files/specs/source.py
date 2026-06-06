from __future__ import annotations

import dataclasses
import typing as t

from mountainash_files.specs.base import FileSpec


@dataclasses.dataclass(frozen=True)
class FileSourceSpec(FileSpec):
    """Read-side: where to get data from."""

    glob: str | None = None
    on_missing: t.Literal["skip", "raise"] = "raise"
