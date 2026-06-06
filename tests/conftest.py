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
def create_xlsx_fixture():
    path = FIXTURES / "sample.xlsx"
    if not path.exists():
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "age", "city"])
            ws.append(["Alice", 30, "London"])
            ws.append(["Bob", 25, "Paris"])
            ws.append(["Charlie", 35, "Berlin"])
            wb.save(path)
        except ImportError:
            pytest.skip("openpyxl required to create XLSX fixture")
    yield
