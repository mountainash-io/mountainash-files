from __future__ import annotations

import fnmatch
import typing as t
from pathlib import Path

from mountainash_transport import StorageFacade

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport import StorageProfileProtocol


def resolve_glob(
    base_path: str,
    pattern: str,
    *,
    storage_profile: "StorageProfileProtocol | None" = None,
    auth_profile: "AuthProfile | None" = None,
) -> list[str]:
    """Resolve a glob pattern against a base path.

    Returns a sorted list of matching file paths (not directories).
    Callers pass already-materialised profile objects — name resolution
    happens once, upstream in the operation entry points.
    """
    if _is_remote(base_path):
        return _resolve_remote_glob(base_path, pattern, storage_profile, auth_profile)
    return _resolve_local_glob(base_path, pattern)


def _resolve_local_glob(base_path: str, pattern: str) -> list[str]:
    base = Path(base_path)
    if not base.is_dir():
        return []
    return sorted(str(p) for p in base.glob(pattern) if p.is_file())


def _resolve_remote_glob(
    base_path: str,
    pattern: str,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
) -> list[str]:
    facade = StorageFacade.from_path(
        base_path, storage_profile, auth_profile=auth_profile
    )
    listing = facade.list_objects(base_path, delimiter=None)
    return sorted(
        entry.path
        for entry in listing.objects
        if fnmatch.fnmatch(entry.path.split("/")[-1], pattern)
    )


def _is_remote(path: str) -> bool:
    return "://" in path
