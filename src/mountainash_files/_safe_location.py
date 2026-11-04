"""What a files error may show of a location (W8).

Built from parts known to be safe rather than by masking known secrets, so an
unforeseen credential shape is dropped, not shown.
"""
from __future__ import annotations

import os
import re

REDACTED = "***"

# A URI scheme at the start of the string (RFC 3986), anchored so the scan is linear.
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")
# Leading C0 controls and space, and embedded tab/CR/LF, are discarded as urllib does.
_C0_OR_SPACE = "".join(chr(c) for c in range(0x21))


def safe_location(location: str | os.PathLike[str]) -> str:
    """Return the part of *location* an error may show.

    - ``scheme://…`` or ``//…``: scheme, host, port and path only; userinfo
      (to the last ``@`` of the authority), query and fragment are dropped.
    - Any other string starting with a scheme (``s3:bucket``, ``user:pass@host/x``):
      ``***``, since none of it is known to be safe.
    - Otherwise a local path (including ``C:/`` or ``C:\\`` drives): unchanged.
    """
    text = os.fspath(location).lstrip(_C0_OR_SPACE)
    for character in "\t\r\n":
        text = text.replace(character, "")
    scheme = _SCHEME.match(text)
    if text.startswith("//"):
        start = 2
    elif scheme is None:
        return text
    elif text.startswith("//", scheme.end()):
        start = scheme.end() + 2
    elif scheme.end() == 2 and text[2:3] in ("/", "\\"):
        return text  # drive letter
    else:
        return REDACTED
    end = len(text)
    for delimiter in "/?#":
        index = text.find(delimiter, start, end)
        if index != -1:
            end = index
    host_start = text.rfind("@", start, end) + 1 or start
    path_end = len(text)
    for delimiter in "?#":
        index = text.find(delimiter, end, path_end)
        if index != -1:
            path_end = index
    return f"{text[:start]}{text[host_start:end]}{text[end:path_end]}"
