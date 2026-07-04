class WriteError(Exception):
    """Write operation failed — incompatible data/format, unsupported
    append, missing path, or serialisation failure."""


class MissingDependencyError(Exception):
    """An optional dependency required for this operation is not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        self.feature = feature
        self.extra = extra
        super().__init__(
            f"{feature} requires an optional dependency. "
            f"Install with: pip install 'mountainash-files[{extra}]'"
        )
