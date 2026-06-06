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
