"""Credential redaction for locations shown in errors (W8)."""
from __future__ import annotations

import os

REDACTED = "***"


def redact_location(location: str | os.PathLike[str]) -> str:
    """Mask the userinfo and every query value of one location; keys, host and path stay.

    Matches mountainash-transport's location redaction. With ``//`` the userinfo
    runs to the last ``@`` of the authority, as ``urllib.parse.urlsplit`` reads it
    (``scheme://user:pw@host`` and ``//user:pw@host``). Without ``//``, a first
    segment holding an ``@`` (``user:pass@host/x``, ``s3:user:pw@bucket``) has that
    prefix masked. Other local paths are returned unchanged.
    """
    text = os.fspath(location)
    slashes = text.find("//")
    start = slashes + 2 if slashes >= 0 else 0
    end = len(text)
    for delimiter in "/?#":
        index = text.find(delimiter, start, end)
        if index != -1:
            end = index
    at = text.rfind("@", start, end)
    if at != -1:
        text = f"{text[:start]}{REDACTED}{text[at:]}"
    query = text.find("?", start)
    fragment = text.find("#", start)
    if query == -1 or fragment != -1 and fragment < query:
        return text
    fragment = text.find("#", query)
    stop = len(text) if fragment == -1 else fragment
    masked = "&".join(
        f"{part.split('=', 1)[0]}={REDACTED}" if "=" in part else (REDACTED if part else part)
        for part in text[query + 1 : stop].split("&")
    )
    return f"{text[: query + 1]}{masked}{text[stop:]}"
