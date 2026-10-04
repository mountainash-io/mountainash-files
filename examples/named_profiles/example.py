"""Use a configured local store by name and as an explicitly resolved pair."""

import os
import tempfile
from pathlib import Path

import pyarrow as pa
from mountainash_settings import SettingsParameters
from mountainash_transport import resolve_storage

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

HERE = Path(__file__).resolve().parent
SALES = [{"region": "north", "total": 120}, {"region": "south", "total": 95}]


def main() -> None:
    config = str(HERE / "profiles.yaml")
    previous = os.environ.get("MOUNTAINASH_PROFILES_CONFIG")
    os.environ["MOUNTAINASH_PROFILES_CONFIG"] = config
    try:
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "sales.csv")
            write(
                FileSinkSpec(path=path, storage_profile="reports"),
                pa.Table.from_pylist(SALES),
            )
            named, = parse(
                FileSourceSpec(path=path, storage_profile="reports"), output="pydata",
            )

            parameters = SettingsParameters.create(config_files=[config])
            storage, auth = resolve_storage("reports", settings_parameters=parameters)
            resolved, = parse(
                FileSourceSpec(path=path, storage_profile=storage, auth_profile=auth),
                output="pydata",
            )
            assert named.data == resolved.data == SALES
            assert type(auth).__name__ == "NoAuthProfile"
            print("reports: local storage with NoAuthProfile")
            print("named and resolved profiles: 2 matching rows")
    finally:
        if previous is None:
            os.environ.pop("MOUNTAINASH_PROFILES_CONFIG", None)
        else:
            os.environ["MOUNTAINASH_PROFILES_CONFIG"] = previous


if __name__ == "__main__":
    main()
