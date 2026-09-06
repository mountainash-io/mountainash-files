from __future__ import annotations

import dataclasses
from typing import Any, BinaryIO, ClassVar

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class XmlSpec(FormatSpec):
    FORMAT: ClassVar[str] = "xml"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".xml",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("application/xml", "text/xml")
    TABULAR: ClassVar[bool] = False

    xpath: str | None = None
    encoding: str | None = None


def xml_parse(data: bytes | BinaryIO, spec: XmlSpec) -> Any:
    if hasattr(data, "read"):
        raw = data.read()
    else:
        raw = data

    if len(raw) == 0:
        raise ParseError("xml", "Empty input")

    try:
        from lxml import etree
        parser = etree.XMLParser(encoding=spec.encoding) if spec.encoding else None
        root = etree.fromstring(raw, parser=parser)
    except ImportError:
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ParseError("xml", str(exc)) from exc
    except Exception as exc:
        raise ParseError("xml", str(exc)) from exc

    if spec.xpath is not None:
        return root.findall(spec.xpath)

    return root


def xml_serialise(data: Any, spec: XmlSpec) -> bytes:
    try:
        from lxml import etree
        if isinstance(data, etree._Element):
            return etree.tostring(data, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    except ImportError:
        pass

    import xml.etree.ElementTree as ET
    return ET.tostring(data, encoding="unicode", xml_declaration=True).encode("utf-8")


register_format(XmlSpec, xml_parse, serialiser=xml_serialise)
