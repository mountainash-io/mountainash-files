from pathlib import Path

import pytest

from mountainash_files.formats.xml import XmlSpec, xml_parse
from mountainash_files.formats._exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


class TestXmlSpec:
    def test_defaults(self):
        spec = XmlSpec()
        assert spec.FORMAT == "xml"
        assert spec.xpath is None
        assert spec.encoding is None

    def test_suffixes(self):
        assert XmlSpec.SUFFIXES == (".xml",)


class TestXmlParse:
    def test_from_fixture(self):
        data = (FIXTURES / "sample.xml").read_bytes()
        element = xml_parse(data, XmlSpec())
        assert element.tag == "people"
        assert len(element.findall("person")) == 3

    def test_from_bytes(self):
        data = b"<root><item>hello</item></root>"
        element = xml_parse(data, XmlSpec())
        assert element.tag == "root"
        assert element.find("item").text == "hello"

    def test_with_xpath(self):
        data = (FIXTURES / "sample.xml").read_bytes()
        elements = xml_parse(data, XmlSpec(xpath=".//person"))
        # xpath returns a list of matched elements
        assert isinstance(elements, list)
        assert len(elements) == 3
        assert elements[0].get("name") == "Alice"

    def test_empty_raises(self):
        with pytest.raises(ParseError, match="xml"):
            xml_parse(b"", XmlSpec())

    def test_malformed_raises(self):
        with pytest.raises(ParseError, match="xml"):
            xml_parse(b"<not-closed>", XmlSpec())

    def test_from_stream(self):
        import io
        data = io.BytesIO(b"<root/>")
        element = xml_parse(data, XmlSpec())
        assert element.tag == "root"


class TestXmlExternalEntities:
    """CVE-2026-41066: lxml < 6.1 resolves external entities by default; the floor is >=6.1.0."""

    SENTINEL = "XXE-SENTINEL-7f3a"

    def _xxe(self, path: Path) -> bytes:
        return (
            f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file://{path}">]>'
            "<r>&x;</r>"
        ).encode()

    @pytest.mark.parametrize("spec", [XmlSpec(), XmlSpec(encoding="UTF-8")])
    def test_external_entity_does_not_read_local_files(self, tmp_path, spec):
        secret = tmp_path / "secret.txt"
        secret.write_text(self.SENTINEL)
        try:
            root = xml_parse(self._xxe(secret), spec)
        except ParseError as exc:
            assert self.SENTINEL not in str(exc)  # rejecting the document is safe
            return
        assert self.SENTINEL not in (root.text or "")

    def test_internal_entities_still_expand(self):
        data = b'<!DOCTYPE r [<!ENTITY e "hello">]><r>&e;</r>'
        assert xml_parse(data, XmlSpec()).text == "hello"
