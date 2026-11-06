"""What a files error may show (W8 safe-location display design).

Errors show only parts known to be safe, built up from the input rather than
masked down from it, so a credential shape nobody anticipated is left out.
"""
from __future__ import annotations

import os
import re

REDACTED = "***"

# An RFC 3986 scheme at the start of the string; anchored, so matching is linear.
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")
_C0_OR_SPACE = "".join(chr(code) for code in range(0x21))


def _first(text: str, characters: str, start: int, end: int) -> int:
    """Index of the first of *characters* in text[start:end], or *end*."""
    found = end
    for character in characters:
        index = text.find(character, start, found)
        if index != -1:
            found = index
    return found


def safe_location(location: str | os.PathLike[str]) -> str:
    """Return the part of *location* an error may show.

    ``scheme://…`` and ``//…``: scheme, host, port and path; userinfo (to the
    last ``@`` of the authority), query and fragment are left out. Any other
    string that starts with a scheme: ``***``. Anything else is a local path
    (including ``C:/`` and ``C:\\`` drives) and is returned unchanged.
    """
    text = os.fspath(location).lstrip(_C0_OR_SPACE)
    for character in "\t\r\n":
        text = text.replace(character, "")
    scheme = _SCHEME.match(text)
    if text.startswith("//"):
        authority_start = 2
    elif scheme is None:
        return text
    elif text.startswith("//", scheme.end()):
        authority_start = scheme.end() + 2
    elif scheme.end() == 2 and text[2:3] in ("/", "\\"):
        return text  # Windows drive letter
    else:
        return REDACTED
    authority_end = _first(text, "/?#", authority_start, len(text))
    at = text.rfind("@", authority_start, authority_end)
    host_start = authority_start if at == -1 else at + 1
    path_end = _first(text, "?#", authority_end, len(text))
    return text[:authority_start] + text[host_start:authority_end] + text[authority_end:path_end]


def _is_trusted_error(exc: BaseException) -> bool:
    """Files errors whose message and attributes are built under the W8 rule."""
    from mountainash_files.formats._exceptions import (
        FormatResolutionError,
        UnknownFormatError,
    )

    return type(exc) in (UnknownFormatError, FormatResolutionError)


def safe_cause(exc: BaseException) -> BaseException | None:
    """The exception an error may chain as ``__cause__`` in place of *exc*, if any.

    OSError: a fresh exception of the same type with only ``errno`` and
    ``strerror``, so the filename is unreachable. Trusted files errors: *exc*.
    Anything else: ``None``; raise outside the ``except`` block so that
    ``__context__`` stays empty too.
    """
    if isinstance(exc, OSError):
        if exc.errno is None:
            return None
        try:
            return type(exc)(exc.errno, exc.strerror)
        except TypeError:  # a subclass whose constructor takes other arguments
            return OSError(exc.errno, exc.strerror)
    return exc if _is_trusted_error(exc) else None


def safe_detail(exc: BaseException) -> str:
    """Native exception text an error may show (spec section 2).

    OSError: ``[Errno N] strerror`` only, never the filename. Trusted files
    errors: their message. Anything else: the class name.
    """
    if isinstance(exc, OSError):
        if exc.errno is None:
            return type(exc).__name__
        return f"[Errno {exc.errno}] {exc.strerror}"
    if _is_trusted_error(exc):
        return str(exc)
    return type(exc).__name__
