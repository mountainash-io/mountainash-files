from __future__ import annotations

import dataclasses
import typing as t

from mountainash_transport import POLICY_UNSET

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport import Pipeline, StorageProfileProtocol
    from mountainash_transport import PolicyOverride

    from mountainash_files.formats._types import FormatSpec
    from mountainash_files.specs.archive import GzipCompression, ZipArchive


@dataclasses.dataclass(frozen=True)
class FileSpec:
    """A file somewhere with a format, storage profile, and auth.

    ``storage_profile`` accepts a materialised profile object, a profile
    name (resolved via ``mountainash_transport.resolve_storage``), or None
    (provider detected from the path scheme, anonymous access). An explicit
    ``auth_profile`` object always overrides a name-resolved one.

    ``policy`` is a location-policy override: omitted (``POLICY_UNSET``) inherits the
    storage profile's ``LOCATION_POLICY``, ``None`` disables confinement and a
    ``LocationPolicy`` replaces the profile's. It is passed unchanged to every storage
    facade the operations create.
    """

    path: str
    format: str | FormatSpec | None = None
    storage_profile: StorageProfileProtocol | str | None = None
    auth_profile: AuthProfile | None = None
    archive: ZipArchive | GzipCompression | None = None
    transforms: Pipeline | None = None
    policy: PolicyOverride = POLICY_UNSET
