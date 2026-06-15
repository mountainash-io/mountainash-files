from __future__ import annotations

import fnmatch
from pathlib import Path

from mountainash_transport import StorageFacade

from mountainash_files._operations import _resolve_auth


def resolve_glob(
    base_path: str,
    pattern: str,
    *,
    auth_profile: str | None = None,
) -> list[str]:
    """Resolve a glob pattern against a base path.

    Returns a sorted list of matching file paths (not directories).
    """
    if _is_remote(base_path):
        return _resolve_remote_glob(base_path, pattern, auth_profile)
    return _resolve_local_glob(base_path, pattern)


def _resolve_local_glob(base_path: str, pattern: str) -> list[str]:
    base = Path(base_path)
    if not base.is_dir():
        return []
    matches = sorted(
        str(p) for p in base.glob(pattern) if p.is_file()
    )
    return matches


def _resolve_remote_glob(
    base_path: str,
    pattern: str,
    auth_profile: str | None,
) -> list[str]:
    profile, auth = _resolve_auth(auth_profile)
    facade = StorageFacade.from_path(base_path, profile=profile, auth=auth)
    file_list = facade.list_files(base_path)
    matches = sorted(
        f.path for f in file_list if fnmatch.fnmatch(f.path.split("/")[-1], pattern)
    )
    return matches


def _is_remote(path: str) -> bool:
    return "://" in path
