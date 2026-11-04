"""Credential redaction for locations shown in errors (W8)."""
from __future__ import annotations

REDACTED = "***"


def redact_location(location: str) -> str:
    """Mask URL userinfo and every query value in *location*; keys, host and path stay.

    Userinfo ends at the last ``@`` of the authority, as ``urllib.parse.urlsplit``
    reads it. Without ``://``, a first path segment of the form ``user:pass@host``
    is treated as userinfo; other local paths are returned unchanged.
    """
    start = location.find("://")
    if start < 0:
        segment = location.split("/", 1)[0]
        at = segment.rfind("@")
        if at > 0 and ":" in segment[:at]:
            return f"{REDACTED}{location[at:]}"
        return location
    start += 3
    end = len(location)
    for delimiter in "/?#":
        index = location.find(delimiter, start, end)
        if index != -1:
            end = index
    at = location.rfind("@", start, end)
    if at != -1:
        location = f"{location[:start]}{REDACTED}{location[at:]}"
    query = location.find("?", start)
    first_fragment = location.find("#", start)
    if query == -1 or first_fragment != -1 and first_fragment < query:
        return location
    fragment = location.find("#", query)
    stop = len(location) if fragment == -1 else fragment
    masked = "&".join(
        f"{part.split('=', 1)[0]}={REDACTED}" if "=" in part else (REDACTED if part else part)
        for part in location[query + 1 : stop].split("&")
    )
    return f"{location[: query + 1]}{masked}{location[stop:]}"
