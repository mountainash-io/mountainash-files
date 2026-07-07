from __future__ import annotations


class FormatError(Exception):
    """Base for all format detection and parsing errors."""


class UnknownFormatError(FormatError):
    """Format cannot be determined. Carries known_suffixes for remediation."""

    def __init__(
        self,
        *,
        path: str | None,
        known_suffixes: tuple[str, ...],
        failed_plugins: tuple[str, ...] = (),
        failures: dict[str, Exception] | None = None,
    ):
        self.path = path
        self.known_suffixes = known_suffixes
        self.failed_plugins = failed_plugins
        msg = (
            f"Cannot determine format from path={path!r}. "
            f"Known suffixes: {', '.join(known_suffixes)}."
        )
        if failed_plugins:
            details = "; ".join(
                f"{name}: {type(exc).__name__}: {exc}"
                for name, exc in sorted((failures or {}).items())
            )
            msg += f" Note: format plugin(s) failed to load — {details}"
        super().__init__(msg)


class ParseError(FormatError):
    """A parser failed to parse the input."""

    def __init__(self, format_key: str, message: str):
        self.format_key = format_key
        super().__init__(f"[{format_key}] {message}")


class FormatConflictError(FormatError):
    """Registering a format that already exists without override=True."""


class FormatResolutionError(FormatError):
    """A lazy format reference failed to resolve at use time."""

    def __init__(self, *, format_key: str, ref: str, field: str):
        self.format_key = format_key
        self.ref = ref
        self.field = field
        super().__init__(
            f"Failed to resolve {field} for format {format_key!r}: {ref}"
        )
