"""Secret-free file-provider access parameters and late resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mountainash_settings import SettingsParameters


@dataclass(frozen=True)
class FileAccessParameters:
    """Configuration handles retained by a file provider, never by a read plan."""

    storage: SettingsParameters | str | None = None
    auth: SettingsParameters | None = None


def resolve_file_access(parameters: FileAccessParameters) -> tuple[Any | None, Any | None]:
    """Resolve settings immediately before a resource read."""
    storage = parameters.storage
    auth = parameters.auth
    if isinstance(storage, SettingsParameters):
        storage = storage.get_settings()
    elif isinstance(storage, str):
        from mountainash_transport import resolve_storage

        storage, discovered_auth = resolve_storage(storage)
        if auth is None:
            auth = discovered_auth
    if isinstance(auth, SettingsParameters):
        auth = auth.get_settings()
    return storage, auth


__all__ = ["FileAccessParameters", "resolve_file_access"]
