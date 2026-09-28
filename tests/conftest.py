import gzip
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def create_parquet_fixture():
    path = FIXTURES / "sample.parquet"
    if not path.exists():
        table = pa.table({
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
            "city": ["London", "Paris", "Berlin"],
        })
        pq.write_table(table, path)
    yield


@pytest.fixture(scope="session", autouse=True)
def create_archive_fixtures():
    csv_data = (FIXTURES / "sample.csv").read_bytes()
    gz_path = FIXTURES / "sample.csv.gz"
    if not gz_path.exists():
        gz_path.write_bytes(gzip.compress(csv_data))

    zip_path = FIXTURES / "sample.zip"
    if not zip_path.exists():
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/sample.csv", csv_data)
            zf.writestr("data/readme.txt", b"test readme")
    yield
