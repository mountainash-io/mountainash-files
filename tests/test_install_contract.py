"""Resolver-facing migration contract and core-only test isolation."""

from importlib.metadata import metadata
from pathlib import Path
import shutil
import subprocess
import sys

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name


def test_supported_python_matches_migrated_transport():
    supported = SpecifierSet(metadata("mountainash-files")["Requires-Python"])
    assert "3.11" not in supported
    assert "3.12" in supported
    assert "3.13" in supported


def test_transport_dependency_and_forwarded_extras_share_candidate_range():
    requirements = [
        Requirement(raw)
        for raw in metadata("mountainash-files").get_all("Requires-Dist", [])
    ]
    transport = [
        req for req in requirements
        if canonicalize_name(req.name) == "mountainash-transport"
    ]
    assert sum(req.marker is None for req in transport) == 1
    for extra in ("", "s3", "gcs", "azure", "sftp", "encryption"):
        active = [
            req for req in transport
            if (
                req.marker is None if not extra else
                req.extras == {extra} and req.marker.evaluate({"extra": extra})
            )
        ]
        assert len(active) == 1
        req = active[0]
        assert req.marker is None or req.marker.evaluate({"extra": extra})
        assert "26.7.0" in req.specifier
        assert "26.6.0" not in req.specifier
        assert "27.0.0" not in req.specifier
    assert all(canonicalize_name(req.name) != "mountainash-secrets" for req in requirements)


def test_core_tests_run_without_xlsx_fixture_or_engine(tmp_path):
    """Missing optional fixture generation must not skip unrelated core work."""
    shutil.copyfile(Path(__file__).with_name("conftest.py"), tmp_path / "conftest.py")
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "sample.csv").write_text("value\n7\n")
    (tmp_path / "test_probe.py").write_text(
        "import sys\n"
        "sys.modules['openpyxl'] = None\n"
        "def test_parse():\n"
        "    from mountainash_files import parse_bytes\n"
        "    assert parse_bytes(b'value\\n7\\n', 'csv').data.to_pylist() == [{'value': 7}]\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_probe.py"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout, result.stdout + result.stderr
