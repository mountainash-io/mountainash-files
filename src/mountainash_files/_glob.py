from __future__ import annotations

import typing as t
from fnmatch import fnmatchcase

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
    """Sorted paths of the files beneath *base_path* whose relative path matches *pattern*.

    One rule for every backend: ``*``, ``?`` and ``[...]`` match within one path segment and
    ``**`` matches zero or more segments. Listing goes through transport's ``list_objects``;
    callers pass already-materialised profile objects.
    """
    parts = [p for p in pattern.split("/") if p not in ("", ".")]
    base = base_path if base_path.endswith("/") else base_path + "/"
    facade = StorageFacade.from_path(base, storage_profile, auth_profile=auth_profile)
    level = facade.list_objects(base, delimiter="/")
    if len(parts) == 1 and parts[0] != "**":
        return sorted(e.path for e in level.objects if e.name and fnmatchcase(e.name, parts[0]))
    # Object stores may hold empty-named "directory marker" keys; they are not files.
    first = next((e for e in (*level.objects, *level.common_prefixes) if e.name), None)
    if first is None:
        return []
    # Backends render paths differently (absolute local paths, s3:// keys), so take the root
    # from an entry rather than rebuilding it from base_path.
    root = first.path.rstrip("/")[: -len(first.name)]
    return sorted(
        e.path for e in facade.list_objects(base, delimiter=None).objects
        if e.name and e.path.startswith(root) and _matches(e.path[len(root):].split("/"), parts)
    )


def _matches(segments: list[str], parts: list[str]) -> bool:
    if not parts:
        return not segments
    if parts[0] == "**":
        return any(_matches(segments[i:], parts[1:]) for i in range(len(segments) + 1))
    return bool(segments) and fnmatchcase(segments[0], parts[0]) and _matches(segments[1:], parts[1:])
