"""FormatSpec ClassVar contract + options envelope hooks (spec §1.4/§3.3/§4.2)."""
import dataclasses
import json
from typing import ClassVar

import pytest

from mountainash_files.formats._types import FormatSpec
from mountainash_files.formats.csv import CsvSpec
from mountainash_files.formats.json import JsonSpec
from mountainash_files.formats.parquet import ParquetSpec
from mountainash_files.formats.tsv import TsvSpec
from mountainash_files.formats.xml import XmlSpec
from mountainash_files.formats.xlsx import XlsxSpec


def test_classvar_defaults():
    assert FormatSpec.TABULAR is True
    assert FormatSpec.COMPLEX_HANDLER_KEY is None
    assert FormatSpec.APPENDABLE is False
    assert FormatSpec.MEDIATYPES == ()


def test_xml_is_non_tabular():
    assert XmlSpec.TABULAR is False


def test_parquet_is_appendable():
    assert ParquetSpec.APPENDABLE is True


@pytest.mark.parametrize(
    "spec_cls, mediatype",
    [
        (CsvSpec, "text/csv"),
        (TsvSpec, "text/tab-separated-values"),
        (JsonSpec, "application/json"),
        (JsonSpec, "application/x-ndjson"),
        (ParquetSpec, "application/vnd.apache.parquet"),
        (ParquetSpec, "application/x-parquet"),
        (
            XlsxSpec,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (XmlSpec, "application/xml"),
        (XmlSpec, "text/xml"),
    ],
)
def test_builtin_mediatypes(spec_cls, mediatype):
    assert mediatype in spec_cls.MEDIATYPES


def test_to_options_emits_non_default_fields_only():
    assert CsvSpec().to_options() == {}
    assert CsvSpec(delimiter=";").to_options() == {"delimiter": ";"}


def test_to_options_skips_default_factory_fields_unless_full() -> None:
    @dataclasses.dataclass(frozen=True)
    class FactorySpec(FormatSpec):
        FORMAT: ClassVar[str] = "factory"
        SUFFIXES: ClassVar[tuple[str, ...]] = ()
        tokens: tuple[str, ...] = dataclasses.field(default_factory=lambda: ("NA",))
        labels: list[str] = dataclasses.field(default_factory=lambda: ["missing"])

    assert FactorySpec().to_options() == {}
    assert FactorySpec().to_options(full=True) == {
        "tokens": ("NA",),
        "labels": ["missing"],
    }


def test_to_options_full_emits_every_field():
    opts = CsvSpec(delimiter=";").to_options(full=True)
    assert opts["delimiter"] == ";"
    assert "quote_char" in opts


def test_from_options_round_trip():
    spec = CsvSpec(delimiter=";", null_sequence="NA")
    rebuilt = CsvSpec.from_options(spec.to_options())
    assert rebuilt == spec


def test_from_options_round_trip_after_json_envelope():
    spec = CsvSpec(dtypes=(("id", "int64"),))
    options = spec.to_options()
    loaded = json.loads(json.dumps(options))
    rebuilt = CsvSpec.from_options(loaded)
    assert rebuilt == spec


@pytest.mark.parametrize(
    "dtypes",
    [
        [["id", "int64", "extra"]],
        [["id"]],
        (("id", "int64", "extra"),),
        (("id",),),
    ],
)
def test_from_options_rejects_malformed_fixed_tuple_arity(dtypes):
    with pytest.raises(ValueError, match="tuple length|arity|dtypes"):
        CsvSpec.from_options({"dtypes": dtypes})


def test_to_options_rejects_non_json_values() -> None:
    @dataclasses.dataclass(frozen=True)
    class BadSpec(FormatSpec):
        FORMAT: ClassVar[str] = "bad"
        SUFFIXES: ClassVar[tuple[str, ...]] = ()
        weird: object = None

    with pytest.raises(ValueError, match="weird"):
        BadSpec(weird=object()).to_options()


def test_tuple_fields_survive_json_check():
    assert CsvSpec(null_sequence="NA").to_options()["null_sequence"] == "NA"
