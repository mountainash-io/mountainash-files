"""XLSX via fastexcel (calamine): bounded row runs keep comment/header rows out of type inference."""
from __future__ import annotations

import io

import pyarrow as pa
import pyarrow.compute as pc

from mountainash_files.formats._exceptions import ParseError

_MAX_EXACT = 2**53


def _runs(excluded: set[int], height: int) -> list[tuple[int, int]]:
    """Contiguous physical data-row runs (start, length) within [0, height)."""
    runs, start = [], 0
    for row in sorted(r for r in excluded if 0 <= r < height):
        if row > start:
            runs.append((start, row - start))
        start = row + 1
    if start < height:
        runs.append((start, height - start))
    return runs


def _merge_type(types: list[pa.DataType]) -> pa.DataType:
    distinct = {t for t in types if not pa.types.is_null(t)}
    if len(distinct) <= 1:
        return distinct.pop() if distinct else pa.null()
    if all(pa.types.is_integer(t) or pa.types.is_floating(t) for t in distinct):
        return pa.float64()
    return pa.string()


def _as(column: pa.ChunkedArray, target: pa.DataType) -> pa.ChunkedArray:
    if column.type == target:
        return column
    if target == pa.string() and pa.types.is_floating(column.type):
        # "1.0" -> "1"; 1.5 -> "1.5"; 1e20 -> "1e+20" (no integer cast of non-integral values)
        return pc.replace_substring_regex(pc.cast(column, pa.string()), r"\.0$", "")
    return pc.cast(column, target)


def _recover_ints(table: pa.Table) -> pa.Table:
    for i, f in enumerate(table.schema):
        if not pa.types.is_floating(f.type):
            continue
        valid = table.column(i).drop_null()
        if len(valid) == 0 or not pc.all(pc.equal(valid, pc.floor(valid))).as_py():
            continue
        if pc.max(valid).as_py() > _MAX_EXACT or pc.min(valid).as_py() < -_MAX_EXACT:
            continue
        table = table.set_column(i, pa.field(f.name, pa.int64(), f.nullable), pc.cast(table.column(i), pa.int64()))
    return table


def _header_cells(raw: bytes, sheet, rows: list[int]) -> list[tuple]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        ws = wb[sheet] if isinstance(sheet, str) else wb.worksheets[sheet]
        wanted, found = set(rows), {}
        for index, row in enumerate(ws.iter_rows(max_row=max(rows) + 1, values_only=True)):
            if index in wanted:
                found[index] = row
        return [found[r] for r in rows]
    finally:
        wb.close()


def read_calamine(raw: bytes, spec) -> pa.Table:
    import fastexcel

    reader = fastexcel.read_excel(raw)
    if spec.sheet_name is not None:
        sheet = spec.sheet_name
    else:
        number = 1 if spec.sheet_number is None else spec.sheet_number
        if number < 1:
            raise ParseError("xlsx", "sheet_number is one-based")
        sheet = number - 1

    def load(**kw) -> pa.Table:
        return pa.Table.from_batches([reader.load_sheet(sheet, header_row=None, **kw).to_arrow()])

    probe = reader.load_sheet(sheet, header_row=None, n_rows=0)
    if probe.total_height == 0 or probe.width == 0:
        return pa.table({})
    # calamine numbers columns from its used range; absolute_index is the sheet column.
    # Leading empty columns are restored below so the table keeps the sheet's shape.
    anchor = probe.available_columns()[0]
    lead = anchor.absolute_index
    # total_height is the used range, which excludes leading blank rows; skip_rows addresses
    # physical rows from the top. A physical load of one column gives the true row numbering.
    first = load(skip_rows=0, use_columns=[anchor.name], dtypes="string").column(0).to_pylist()
    height = len(first)

    comments = {r - 1 for r in spec.comment_rows}
    if spec.comment_char:
        comments |= {i for i, v in enumerate(first) if isinstance(v, str) and v.startswith(spec.comment_char)}

    if height <= len([c for c in comments if 0 <= c < height]):
        return pa.table({})   # every row is a comment: nothing to header or read

    headers: list[int] = []
    if spec.header:
        positions = sorted(set(spec.header_rows)) or [1]
        available = height - len([c for c in comments if 0 <= c < height])
        if positions[0] < 1 or positions[-1] > available:
            raise ParseError("xlsx", "header row is outside the available records")
        logical = 0
        for phys in range(height):
            if phys in comments:
                continue
            logical += 1
            if logical in positions:
                headers.append(phys)
            if len(headers) == len(positions):
                break

    blocks = [load(skip_rows=start, n_rows=n, schema_sample_rows=spec.infer_sample_rows)
              for start, n in _runs(comments | set(headers), height)]
    blocks = [b for b in blocks if b.num_rows]
    width = lead + max([b.num_columns for b in blocks] + [probe.width])
    if spec.header:
        cells = _header_cells(raw, sheet, headers)
        labels = [spec.header_join.join(str(r[i]) for r in cells if i < len(r) and r[i] not in (None, ""))
                  or f"field{i + 1}" for i in range(width)]
        if len(labels) != len(set(labels)):
            raise ParseError("xlsx", "duplicate final header labels")
    else:
        labels = [f"field{i + 1}" for i in range(width)]
    if not blocks:
        return pa.table({label: pa.nulls(0) for label in labels})
    columns = []
    for i in range(width):
        j = i - lead
        if j < 0:
            columns.append(pa.chunked_array([pa.nulls(sum(b.num_rows for b in blocks))]))
            continue
        parts = [b.column(j) if j < b.num_columns else pa.chunked_array([pa.nulls(b.num_rows)]) for b in blocks]
        target = _merge_type([p.type for p in parts])
        columns.append(pa.chunked_array([c for p in parts for c in _as(p, target).chunks], type=target))
    return _recover_ints(pa.Table.from_arrays(columns, names=labels))
