from lxml import etree

from mountainash_files.formats.xml import XmlSpec, xml_serialise


def test_lxml_element():
    root = etree.Element("root")
    child = etree.SubElement(root, "item")
    child.text = "hello"
    result = xml_serialise(root, XmlSpec())
    assert isinstance(result, bytes)
    assert b"hello" in result
