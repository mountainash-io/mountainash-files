"""Entry-point plugin discovery (Draft §3.5/§3.6 + rev-3 §2.1)."""
import types

import pytest

from mountainash_files.formats import _registry
from mountainash_files.formats._exceptions import UnknownFormatError
from mountainash_files.formats._registry import (
    _discover_entrypoint_formats,
    _reset_registry,
    resolve_format,
)


class _FakeEP:
    def __init__(self, name, load=None, error=None):
        self.name = name
        self.value = f"fake_pkg.{name}"
        self.group = "mountainash_files.formats"
        self._load = load
        self._error = error

    def load(self):
        if self._error:
            raise self._error
        return self._load()


@pytest.fixture(autouse=True)
def fresh_registry():
    _reset_registry()
    yield
    _reset_registry()


def _register_toy():
    import dataclasses
    from typing import ClassVar

    from mountainash_files.formats._registry import register_format
    from mountainash_files.formats._types import FormatSpec

    @dataclasses.dataclass(frozen=True)
    class ToySpec(FormatSpec):
        FORMAT: ClassVar[str] = "toy"
        SUFFIXES: ClassVar[tuple[str, ...]] = (".toy",)

    register_format(ToySpec, lambda d, s: {"ok": True})
    return types.ModuleType("fake")


def test_discovery_imports_and_registers(monkeypatch):
    monkeypatch.setattr(
        _registry.importlib.metadata,
        "entry_points",
        lambda group: [_FakeEP("toy", load=_register_toy)],
    )
    _discover_entrypoint_formats()
    assert resolve_format(format="toy") == ("toy", None)


def test_discovery_is_latched(monkeypatch):
    calls = []
    monkeypatch.setattr(
        _registry.importlib.metadata,
        "entry_points",
        lambda group: calls.append(1) or [],
    )
    _discover_entrypoint_formats()
    _discover_entrypoint_formats()
    assert len(calls) == 1


def test_reset_registry_resets_latch(monkeypatch):
    calls = []
    monkeypatch.setattr(
        _registry.importlib.metadata,
        "entry_points",
        lambda group: calls.append(1) or [],
    )
    _discover_entrypoint_formats()
    _reset_registry()
    _discover_entrypoint_formats()
    assert len(calls) == 2


def test_failed_plugin_is_isolated_and_surfaced(monkeypatch):
    boom = ModuleNotFoundError("No module named 'fake_pkg'")
    monkeypatch.setattr(
        _registry.importlib.metadata,
        "entry_points",
        lambda group: [
            _FakeEP("broken", error=boom),
            _FakeEP("toy", load=_register_toy),
        ],
    )
    _discover_entrypoint_formats()
    assert resolve_format(format="toy") == ("toy", None)
    with pytest.raises(UnknownFormatError, match="broken"):
        resolve_format(format="nope")
    with pytest.raises(UnknownFormatError, match="broken"):
        resolve_format(path="data.unknownsuffix")
