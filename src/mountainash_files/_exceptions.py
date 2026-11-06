from typing import TYPE_CHECKING

from mountainash_files._safe_location import safe_location

if TYPE_CHECKING:
    import pyarrow as pa


class WriteError(Exception):
    """Write operation failed — incompatible data/format, unsupported
    append, missing path, or serialisation failure."""


class AppendSchemaMismatchError(WriteError):
    """Append input does not match the destination's ordered names and types."""

    def __init__(
        self, path: str, expected_schema: "pa.Schema", actual_schema: "pa.Schema"
    ) -> None:
        self.path = safe_location(path)
        self.expected_schema = expected_schema
        self.actual_schema = actual_schema
        super().__init__(
            f"Append schema mismatch for {self.path!r}: expected {expected_schema}, got {actual_schema}"
        )


class MissingDependencyError(Exception):
    """An optional dependency required for this operation is not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        self.feature = feature
        self.extra = extra
        super().__init__(
            f"{feature} requires an optional dependency. "
            f"Install with: pip install 'mountainash-files[{extra}]'"
        )
