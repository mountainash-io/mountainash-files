"""Decision 385 extended to xlsx: bounded decompression before any engine sees the bytes."""
from __future__ import annotations

import io
import struct
import tracemalloc
import zipfile
from pathlib import Path

import pytest

from mountainash_files import FileSourceSpec, parse
from mountainash_files._archives import ArchiveLimitError
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.xlsx import (
    DEFAULT_XLSX_MAX_DECOMPRESSED_BYTES,
    DEFAULT_XLSX_MAX_MEMBERS,
    XlsxSpec,
    xlsx_inspect_schema,
    xlsx_parse,
)

openpyxl = pytest.importorskip("openpyxl")

FIXTURES = Path(__file__).parent / "fixtures"
MIB = 1024 * 1024
SMALL_LIMIT = MIB
BOMB = 64 * MIB  # of zeros: compresses to ~64 KiB
PEAK_CEILING = 16 * MIB  # far below BOMB; chunk-sized in practice


def _book() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([1, 2.5])
    ws.append([2, 3.5])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_zeros(zf: zipfile.ZipFile, name: str, size: int) -> None:
    """Stream *size* zero bytes into a member without holding them all."""
    block = b"\0" * MIB
    with zf.open(name, "w", force_zip64=True) as out:
        for _ in range(size // MIB):
            out.write(block)
        out.write(b"\0" * (size % MIB))


def book_with_padding(size: int, name: str = "xl/padding.bin") -> bytes:
    """A valid workbook plus a highly compressible member the engines never read."""
    buf = io.BytesIO(_book())
    with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_zeros(zf, name, size)
    return buf.getvalue()


def book_with_inflated_sheet(extra: int) -> bytes:
    """A valid workbook whose sheet XML is followed by *extra* bytes of whitespace."""
    src = zipfile.ZipFile(io.BytesIO(_book()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for info in src.infolist():
            if info.filename == "xl/worksheets/sheet1.xml":
                with zf.open(info.filename, "w", force_zip64=True) as out:
                    out.write(src.read(info))
                    block = b" " * MIB
                    for _ in range(extra // MIB):
                        out.write(block)
            else:
                zf.writestr(info, src.read(info))
    return buf.getvalue()


def book_with_member_count(extra: int) -> bytes:
    buf = io.BytesIO(_book())
    with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(extra):
            zf.writestr(f"xl/extra/{i}.bin", b"")
    return buf.getvalue()


def forge_declared_size(raw: bytes, member: str, declared: int) -> bytes:
    """Rewrite the uncompressed size in both the local header and central directory."""
    out = bytearray(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        info = zf.getinfo(member)
    name = member.encode()
    local = info.header_offset
    assert out[local : local + 4] == b"PK\x03\x04"
    # zip64 entries keep sizes in an extra field: neutralise by patching the 32-bit fields
    # (zipfile reads the central directory's 32-bit field unless it is 0xFFFFFFFF).
    central = out.index(b"PK\x01\x02")
    while True:
        fname_len = struct.unpack_from("<H", out, central + 28)[0]
        if bytes(out[central + 46 : central + 46 + fname_len]) == name:
            break
        central = out.index(b"PK\x01\x02", central + 4)
    struct.pack_into("<I", out, central + 24, declared)
    struct.pack_into("<I", out, central + 20, 1)  # compressed size
    struct.pack_into("<I", out, local + 22, declared)
    return bytes(out)


def _via_parse(data: bytes, spec: XlsxSpec, tmp_path: Path):
    path = tmp_path / "book.xlsx"
    path.write_bytes(data)
    return parse(FileSourceSpec(path=str(path), format=spec))


ENTRY_POINTS = {
    "xlsx_parse": lambda data, spec, tmp: xlsx_parse(data, spec),
    "xlsx_parse_stream": lambda data, spec, tmp: xlsx_parse(io.BytesIO(data), spec),
    "xlsx_inspect_schema": lambda data, spec, tmp: xlsx_inspect_schema(data, spec),
    "parse": lambda data, spec, tmp: _via_parse(data, spec, tmp),
}


def _peak_of(call) -> int:
    tracemalloc.start()
    try:
        call()
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return peak


class TestSpecLimits:
    def test_defaults(self):
        spec = XlsxSpec()
        assert spec.max_decompressed_bytes == 512 * MIB == DEFAULT_XLSX_MAX_DECOMPRESSED_BYTES
        assert spec.max_members == 1_000 == DEFAULT_XLSX_MAX_MEMBERS

    @pytest.mark.parametrize("field", ["max_decompressed_bytes", "max_members"])
    @pytest.mark.parametrize("bad", [0, -1, True, 1.5, "10", None])
    def test_invalid_values_rejected(self, field, bad):
        with pytest.raises(ValueError, match=field):
            XlsxSpec(**{field: bad})

    def test_configurable(self):
        spec = XlsxSpec(max_decompressed_bytes=10, max_members=2)
        assert (spec.max_decompressed_bytes, spec.max_members) == (10, 2)


class TestDecompressedSize:
    @pytest.mark.parametrize("entry", ENTRY_POINTS)
    def test_padding_member_over_limit_rejected_with_small_peak(self, entry, tmp_path):
        data = book_with_padding(BOMB)
        spec = XlsxSpec(max_decompressed_bytes=SMALL_LIMIT)
        run = ENTRY_POINTS[entry]
        with pytest.raises(ArchiveLimitError, match="XlsxSpec.max_decompressed_bytes"):
            run(data, spec, tmp_path)
        peak = _peak_of(lambda: _swallow(run, data, spec, tmp_path))
        assert peak < PEAK_CEILING

    def test_inflated_sheet_xml_over_limit_rejected(self):
        data = book_with_inflated_sheet(BOMB)
        with pytest.raises(ArchiveLimitError, match="max_decompressed_bytes"):
            xlsx_parse(data, XlsxSpec(max_decompressed_bytes=SMALL_LIMIT))

    def test_default_limit_rejects_bomb_with_small_peak(self):
        data = book_with_padding(DEFAULT_XLSX_MAX_DECOMPRESSED_BYTES + MIB)
        assert len(data) < 2 * MIB  # it really is a bomb: >512 MiB from ~1 MiB
        peak = _peak_of(lambda: _swallow(xlsx_parse, data, XlsxSpec(), None))
        assert peak < PEAK_CEILING

    def test_limit_is_total_across_members(self):
        data = book_with_padding(600 * 1024, "xl/p1.bin")
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("xl/p2.bin", b"\0" * (600 * 1024))
        # each padding member is under 1 MiB; together with the workbook they are not
        with pytest.raises(ArchiveLimitError):
            xlsx_parse(buf.getvalue(), XlsxSpec(max_decompressed_bytes=MIB))

    def test_forged_central_directory_size_does_not_evade_limit(self):
        data = forge_declared_size(book_with_padding(BOMB), "xl/padding.bin", 10)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert zf.getinfo("xl/padding.bin").file_size == 10  # the directory lies
        peak = _peak_of(lambda: _swallow(xlsx_parse, data, XlsxSpec(max_decompressed_bytes=SMALL_LIMIT), None))
        assert peak < PEAK_CEILING
        with pytest.raises(ArchiveLimitError):
            xlsx_parse(data, XlsxSpec(max_decompressed_bytes=SMALL_LIMIT))

    def test_raising_the_limit_allows_what_the_default_rejects(self):
        data = book_with_padding(8 * MIB)
        with pytest.raises(ArchiveLimitError):
            xlsx_parse(data, XlsxSpec(max_decompressed_bytes=4 * MIB))
        table = xlsx_parse(data, XlsxSpec(max_decompressed_bytes=16 * MIB))
        assert table.to_pylist() == [{"a": 1, "b": 2.5}, {"a": 2, "b": 3.5}]

    def test_limit_exactly_met_is_allowed(self):
        data = book_with_padding(MIB)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total = sum(i.file_size for i in zf.infolist())
        assert xlsx_parse(data, XlsxSpec(max_decompressed_bytes=total)).num_rows == 2
        with pytest.raises(ArchiveLimitError):
            xlsx_parse(data, XlsxSpec(max_decompressed_bytes=total - 1))


class TestMemberCount:
    @pytest.mark.parametrize("entry", ENTRY_POINTS)
    def test_member_count_over_limit_rejected(self, entry, tmp_path):
        data = book_with_member_count(10)
        with pytest.raises(ArchiveLimitError, match="XlsxSpec.max_members"):
            ENTRY_POINTS[entry](data, XlsxSpec(max_members=5), tmp_path)

    def test_default_member_limit_rejects_flood(self):
        data = book_with_member_count(DEFAULT_XLSX_MAX_MEMBERS + 1)
        with pytest.raises(ArchiveLimitError, match="max_members"):
            xlsx_parse(data, XlsxSpec())

    def test_member_count_at_limit_allowed(self):
        data = book_with_member_count(3)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            n = len(zf.infolist())
        assert xlsx_parse(data, XlsxSpec(max_members=n)).num_rows == 2
        with pytest.raises(ArchiveLimitError):
            xlsx_parse(data, XlsxSpec(max_members=n - 1))


class TestUnchangedBehaviour:
    def test_normal_workbook_reads_unchanged(self):
        table = xlsx_parse(_book(), XlsxSpec())
        assert table.to_pylist() == [{"a": 1, "b": 2.5}, {"a": 2, "b": 3.5}]

    def test_fixture_reads_under_defaults(self, tmp_path):
        raw = (FIXTURES / "sample.xlsx").read_bytes()
        assert xlsx_parse(raw, XlsxSpec()).equals(
            xlsx_parse(raw, XlsxSpec(max_decompressed_bytes=1024**4, max_members=10**6))
        )
        assert _via_parse(raw, XlsxSpec(), tmp_path)[0].data.num_rows > 0

    def test_real_workbooks_are_far_below_defaults(self):
        with zipfile.ZipFile(io.BytesIO(_book())) as zf:
            assert len(zf.infolist()) < DEFAULT_XLSX_MAX_MEMBERS / 10

    def test_non_zip_input_still_fails_with_parse_error(self):
        with pytest.raises(ParseError) as info:
            xlsx_parse(b"this is not a workbook", XlsxSpec())
        assert not isinstance(info.value, ArchiveLimitError)

    def test_corrupt_zip_directory_fails_with_parse_error(self):
        raw = bytearray(_book())
        start = raw.index(b"PK\x01\x02")
        raw[start : start + 40] = b"\xff" * 40  # EOCD intact, directory garbage
        with pytest.raises(ParseError):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_truncated_deflate_member_fails_with_parse_error(self):
        raw = bytearray(book_with_padding(64 * 1024))
        with zipfile.ZipFile(io.BytesIO(bytes(raw))) as zf:
            info = zf.getinfo("xl/padding.bin")
        name_len, extra_len = struct.unpack_from("<HH", raw, info.header_offset + 26)
        mid = info.header_offset + 30 + name_len + extra_len + 2  # inside the deflate stream
        raw[mid : mid + 16] = b"\xff" * 16
        with pytest.raises(ParseError):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_unsupported_compression_method_rejected(self):
        buf = io.BytesIO(_book())
        with zipfile.ZipFile(buf, "a") as zf:
            zf.writestr("xl/odd.bin", b"x" * 100, compress_type=zipfile.ZIP_BZIP2)
        with pytest.raises(ParseError, match="compression"):
            xlsx_parse(buf.getvalue(), XlsxSpec())


class TestAmbiguousDirectory:
    """Containers whose directory different readers could walk differently are refused.

    zipfile walks the central directory by declared byte size; other readers may walk it by
    declared entry count or pick another end record. Anything that could let a member hide
    from the check is a ParseError, never read by an engine.
    """

    @staticmethod
    def _end(raw: bytes) -> int:
        return raw.rindex(b"PK\x05\x06")

    def test_declared_count_below_real_count_refused(self):
        raw = bytearray(book_with_member_count(3))
        pos = self._end(bytes(raw))
        total = struct.unpack_from("<H", raw, pos + 10)[0]
        struct.pack_into("<HH", raw, pos + 8, total - 1, total - 1)
        with pytest.raises(ParseError, match="declares"):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_declared_count_above_real_count_refused(self):
        raw = bytearray(book_with_member_count(3))
        pos = self._end(bytes(raw))
        total = struct.unpack_from("<H", raw, pos + 10)[0]
        struct.pack_into("<HH", raw, pos + 8, total + 1, total + 1)
        with pytest.raises(ParseError, match="declares"):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_declared_count_over_limit_rejected_before_directory_is_parsed(self):
        raw = bytearray(_book())
        pos = self._end(bytes(raw))
        struct.pack_into("<HH", raw, pos + 8, 60000, 60000)
        with pytest.raises(ArchiveLimitError, match="max_members"):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_prepended_data_refused(self):
        with pytest.raises(ParseError, match="central directory"):
            xlsx_parse(b"junk" * 10 + _book(), XlsxSpec())

    def test_data_after_end_record_refused(self):
        with pytest.raises(ParseError, match="after the end record"):
            xlsx_parse(_book() + b"trailing", XlsxSpec())

    def test_second_end_record_signature_in_directory_refused(self):
        buf = io.BytesIO(_book())
        info = zipfile.ZipInfo("xl/decoy.bin")
        info.comment = b"PK\x05\x06" + b"\0" * 18
        with zipfile.ZipFile(buf, "a") as zf:
            zf.writestr(info, b"")
        with pytest.raises(ParseError, match="more than one end record"):
            xlsx_parse(buf.getvalue(), XlsxSpec())

    def test_truncated_trailing_end_record_signature_refused(self):
        # the last signature is not a whole record; a reader that skips it would use another
        with pytest.raises(ParseError, match="truncated end record"):
            xlsx_parse(_book() + b"PK\x05\x06 tail", XlsxSpec())

    def test_ordinary_zip_comment_allowed(self):
        buf = io.BytesIO(_book())
        with zipfile.ZipFile(buf, "a") as zf:
            zf.comment = b"made by a spreadsheet tool"
        assert xlsx_parse(buf.getvalue(), XlsxSpec()).num_rows == 2

    def test_zip64_directory_checked_and_read(self):
        data = book_with_member_count(70_000)  # more than 65,535 entries: zip64 end record
        assert b"PK\x06\x06" in data
        assert xlsx_parse(data, XlsxSpec(max_members=100_000)).num_rows == 2
        with pytest.raises(ArchiveLimitError, match="max_members"):
            xlsx_parse(data, XlsxSpec(max_members=60_000))

    def test_encrypted_member_refused(self):
        raw = bytearray(_book())
        central = raw.index(b"PK\x01\x02")
        flags = struct.unpack_from("<H", raw, central + 8)[0]
        struct.pack_into("<H", raw, central + 8, flags | 0x1)
        with pytest.raises(ParseError, match="encrypted"):
            xlsx_parse(bytes(raw), XlsxSpec())

    def test_negative_local_header_offset_is_parse_error(self):
        raw = bytearray(_book())
        central = raw.index(b"PK\x01\x02")
        struct.pack_into("<I", raw, central + 42, 0xFFFFFF00)
        with pytest.raises(ParseError):
            xlsx_parse(bytes(raw), XlsxSpec())


def _swallow(run, data, spec, tmp):
    """Call an entry point, expecting the limit error (so the peak covers the rejection)."""
    with pytest.raises(ArchiveLimitError):
        run(data, spec) if tmp is None else run(data, spec, tmp)
