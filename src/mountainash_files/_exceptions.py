class WriteError(Exception):
    """Write operation failed — incompatible data/format, unsupported
    append, missing path, or serialisation failure."""
