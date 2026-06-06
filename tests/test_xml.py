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
