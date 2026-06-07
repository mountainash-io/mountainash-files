from __future__ import annotations

import dataclasses
import typing as t

from mountainash_files.specs.base import FileSpec


@dataclasses.dataclass(frozen=True)
class FileSinkSpec(FileSpec):
    """Write-side: where to put data."""

    write_disposition: t.Literal["replace", "append"] = "replace"
    create_path: bool = True
