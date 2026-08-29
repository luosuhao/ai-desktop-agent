#!/usr/bin/env python3
"""Create an editable PPT content manifest from a mixed Excel workbook."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import posixpath
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900, from_excel


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Excel text/table/image assets into excel-content-manifest.json."
    )
    parser.add_argument("workbook", type=Path, help="Input .xlsx workbook")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory. Defaults to <workbook-stem>_intake beside the workbook.",
    )
    parser.add_argument(
        "--max-sample-rows",
        type=int,
        default=8,
        help="Maximum sample rows saved for each table block.",
    )
    parser.add_argument("--pretty", action="store_true", help="Print compact summary.")
    return parser.parse_args()


def safe_name(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug or fallback


def normalize_part_path(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


def relationships(zf: zipfile.ZipFile, part_path: str) -> dict[str, dict[str, str]]:
    rels_path = posixpath.join(
        posixpath.dirname(part_path),
        "_rels",
        f"{posixpath.basename(part_path)}.rels",
    )
    try:
        root = ET.fromstring(zf.read(rels_path))
    except KeyError:
        return {}
    result: dict[str, dict[str, str]] = {}
    for rel in root.findall(f"{{{NS['rel']}}}Relationship"):
        rel_id = rel.attrib.get("Id")
        if rel_id:
            result[rel_id] = {
                "type": rel.attrib.get("Type", ""),
                "target": rel.attrib.get("Target", ""),
                "targetMode": rel.attrib.get("TargetMode", ""),
            }
    return result


def read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element:
    return ET.fromstring(zf.read(path))


def parse_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = read_xml(zf, "xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    for si in root.findall("main:si", NS):
        parts = [t.text or "" for t in si.findall(".//main:t", NS)]
        strings.append("".join(parts))
    return strings


def col_to_num(col: str) -> int:
    value = 0
    for ch in col:
        value = value * 26 + (ord(ch.upper()) - ord("A") + 1)
    return value


def num_to_col(num: int) -> str:
    result = ""
    while num:
        num, rem = divmod(num - 1, 26)
        result = chr(65 + rem) + result
    return result or "A"


def split_cell_ref(ref: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", ref)
    if not match:
        return 1, 1
    return int(match.group(2)), col_to_num(match.group(1))


def cell_ref(row: int, col: int) -> str:
    return f"{num_to_col(col)}{row}"


def range_ref(min_row: int, min_col: int, max_row: int, max_col: int) -> str:
    if min_row == max_row and min_col == max_col:
        return cell_ref(min_row, min_col)
    return f"{cell_ref(min_row, min_col)}:{cell_ref(max_row, max_col)}"


DATE_BUILTIN_NUM_FMT_IDS = {
    14,
    15,
    16,
    17,
    22,
    27,
    30,
    36,
    45,
    46,
    47,
    50,
    57,
}


def normalize_number_format(format_code: str) -> str:
    code = re.sub(r'"[^"]*"', "", format_code or "")
    code = re.sub(r"\[[^\]]*\]", "", code)
    code = code.replace("\\", "").replace("_", "").replace("*", "").lower()
    return code


def is_date_number_format(format_code: str) -> bool:
    code = normalize_number_format(format_code)
    if not code:
        return False
    if any(token in code for token in ["yyyy", "yy", "年", "月", "日"]):
        return True
    return "d" in code and ("m" in code or "y" in code)


def parse_date_style_ids(zf: zipfile.ZipFile) -> set[int]:
    try:
        root = read_xml(zf, "xl/styles.xml")
    except KeyError:
        return set()
    numfmts: dict[int, str] = {}
    for numfmt in root.findall("main:numFmts/main:numFmt", NS):
        num_fmt_id = numfmt.attrib.get("numFmtId")
        format_code = numfmt.attrib.get("formatCode", "")
        if num_fmt_id:
            numfmts[int(num_fmt_id)] = format_code
    date_style_ids: set[int] = set()
    for index, xf in enumerate(root.findall("main:cellXfs/main:xf", NS)):
        num_fmt_id = int(xf.attrib.get("numFmtId", "0"))
        if num_fmt_id in DATE_BUILTIN_NUM_FMT_IDS or is_date_number_format(numfmts.get(num_fmt_id, "")):
            date_style_ids.add(index)
    return date_style_ids


def workbook_epoch(zf: zipfile.ZipFile) -> Any:
    try:
        root = read_xml(zf, "xl/workbook.xml")
    except KeyError:
        return CALENDAR_WINDOWS_1900
    workbook_pr = root.find("main:workbookPr", NS)
    if workbook_pr is not None and workbook_pr.attrib.get("date1904") in {"1", "true", "True"}:
        return CALENDAR_MAC_1904
    return CALENDAR_WINDOWS_1900


def excel_serial_to_iso(value: float, epoch: Any) -> str:
    converted = from_excel(value, epoch=epoch)
    if getattr(converted, "hour", 0) or getattr(converted, "minute", 0) or getattr(converted, "second", 0):
        return converted.isoformat(sep=" ")
    return converted.date().isoformat()


def cell_value(
    cell: ET.Element,
    shared_strings: list[str],
    date_style_ids: set[int],
    epoch: Any,
) -> tuple[Any, str]:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        text = "".join(t.text or "" for t in cell.findall(".//main:t", NS))
        return text, "text"
    value_elem = cell.find("main:v", NS)
    if value_elem is None:
        return "", "blank"
    raw = value_elem.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)], "text"
        except (ValueError, IndexError):
            return raw, "text"
    if cell_type in {"str", "e"}:
        return raw, "text"
    if cell_type == "b":
        return raw == "1", "boolean"
    try:
        number = float(raw)
        style_id = int(cell.attrib.get("s", "0"))
        if style_id in date_style_ids:
            return excel_serial_to_iso(number, epoch), "date"
        if number.is_integer():
            return int(number), "number"
        return number, "number"
    except ValueError:
        return raw, "text"


def parse_sheet_cells(
    root: ET.Element,
    shared_strings: list[str],
    date_style_ids: set[int],
    epoch: Any,
) -> tuple[dict[tuple[int, int], dict[str, Any]], list[int]]:
    cells: dict[tuple[int, int], dict[str, Any]] = {}
    row_numbers: list[int] = []
    for row in root.findall("main:sheetData/main:row", NS):
        row_index = int(row.attrib.get("r", "0"))
        row_numbers.append(row_index)
        for c in row.findall("main:c", NS):
            ref = c.attrib.get("r", "")
            if not ref:
                continue
            r, col = split_cell_ref(ref)
            value, kind = cell_value(c, shared_strings, date_style_ids, epoch)
            if value == "":
                continue
            formula = c.find("main:f", NS)
            cells[(r, col)] = {
                "ref": ref,
                "value": value,
                "kind": kind,
                "formula": formula.text if formula is not None else None,
            }
    return cells, row_numbers


def parse_merged_ranges(root: ET.Element) -> list[tuple[int, int, int, int, str]]:
    ranges: list[tuple[int, int, int, int, str]] = []
    for merge_cell in root.findall("main:mergeCells/main:mergeCell", NS):
        ref = merge_cell.attrib.get("ref", "")
        parsed = parse_cell_range(ref)
        if parsed:
            min_row, min_col, max_row, max_col = parsed
            ranges.append((min_row, min_col, max_row, max_col, ref))
    return ranges


def display_width(value: Any) -> int:
    width = 0
    for char in str(value or ""):
        if char.isspace():
            width += 1
        elif ord(char) >= 0x2E80:
            width += 2
        else:
            width += 1
    return width


def visual_text_column_span(value: Any) -> int:
    width = display_width(value)
    if width < 12:
        return 1
    return min(10, max(1, ceil(width / 12)))


def occupied_positions_for_detection(
    cells: dict[tuple[int, int], dict[str, Any]],
    merged_ranges: list[tuple[int, int, int, int, str]],
    image_ranges: list[tuple[int, int, int, int]] | None = None,
) -> set[tuple[int, int]]:
    occupied = set(cells)
    actual_by_row: dict[int, set[int]] = {}
    for row, col in cells:
        actual_by_row.setdefault(row, set()).add(col)

    for min_row, min_col, max_row, max_col, _ref in merged_ranges:
        if (min_row, min_col) not in cells:
            continue
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                occupied.add((row, col))

    for (row, col), item in cells.items():
        if item.get("kind") != "text":
            continue
        span = visual_text_column_span(item.get("value", ""))
        if span <= 1:
            continue
        row_actual_cols = actual_by_row.get(row, set())
        for offset in range(1, span):
            target_col = col + offset
            if target_col in row_actual_cols:
                break
            occupied.add((row, target_col))
    for min_row, min_col, max_row, max_col in image_ranges or []:
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                occupied.add((row, col))
    return occupied


def row_bounds(cells: dict[tuple[int, int], dict[str, Any]], row: int) -> tuple[int, int] | None:
    cols = [col for (r, col) in cells if r == row]
    if not cols:
        return None
    return min(cols), max(cols)


def sheet_dimension(root: ET.Element, cells: dict[tuple[int, int], dict[str, Any]]) -> str:
    dim = root.find("main:dimension", NS)
    if dim is not None and dim.attrib.get("ref"):
        return dim.attrib["ref"]
    if not cells:
        return "A1"
    rows = [r for r, _c in cells]
    cols = [c for _r, c in cells]
    return range_ref(min(rows), min(cols), max(rows), max(cols))


def classify_sheet(name: str) -> str:
    if name == "首页信息":
        return "metadata"
    if name.endswith("_数据") or name.endswith("数据"):
        return "data"
    return "report"


def extract_deck_meta(sheet_name: str, cells: dict[tuple[int, int], dict[str, Any]]) -> dict[str, Any]:
    if sheet_name != "首页信息":
        return {}
    meta: dict[str, Any] = {}
    for row in range(1, 40):
        left = cells.get((row, 1), {}).get("value")
        right = cells.get((row, 2), {}).get("value")
        if left not in (None, "") and right not in (None, ""):
            meta[str(left).strip()] = right
    return meta


def row_values(cells: dict[tuple[int, int], dict[str, Any]], row: int, min_col: int, max_col: int) -> list[Any]:
    return [cells.get((row, col), {}).get("value", "") for col in range(min_col, max_col + 1)]


def detect_row_blocks(occupied_positions: set[tuple[int, int]]) -> list[tuple[int, int]]:
    if not occupied_positions:
        return []
    used_rows = sorted({r for r, _c in occupied_positions})
    blocks: list[tuple[int, int]] = []
    start = prev = used_rows[0]
    for row in used_rows[1:]:
        if row <= prev + 1:
            prev = row
        else:
            blocks.append((start, prev))
            start = prev = row
    blocks.append((start, prev))
    return blocks


def detect_rect_blocks(
    cells: dict[tuple[int, int], dict[str, Any]],
    occupied_positions: set[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    """Split a worksheet into rectangular islands separated by empty rows/columns."""
    rects: list[tuple[int, int, int, int]] = []
    for min_row, max_row in detect_row_blocks(occupied_positions):
        used_cols = sorted(
            {
                col
                for row, col in occupied_positions
                if min_row <= row <= max_row
            }
        )
        if not used_cols:
            continue
        col_start = col_prev = used_cols[0]
        for col in used_cols[1:]:
            if col <= col_prev + 1:
                col_prev = col
            else:
                rects.append((min_row, max_row, col_start, col_prev))
                col_start = col_prev = col
        rects.append((min_row, max_row, col_start, col_prev))
    return rects


def numeric_ratio(cells: dict[tuple[int, int], dict[str, Any]], min_row: int, max_row: int, min_col: int, max_col: int) -> float:
    total = 0
    numeric = 0
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            item = cells.get((row, col))
            if not item:
                continue
            total += 1
            if item["kind"] == "number":
                numeric += 1
    return round(numeric / total, 3) if total else 0.0


def classify_cell_block(stats: dict[str, Any], sheet_kind: str) -> tuple[str, str]:
    row_count = stats["rowCount"]
    col_count = stats["colCount"]
    text_ratio = stats["textCellRatio"]
    numeric_ratio_value = stats["numericCellRatio"]
    long_text_count = stats["longTextCellCount"]

    if row_count <= 3:
        return "text_block", "summarize_to_bullets"
    if text_ratio >= 0.9:
        return "text_block", "summarize_to_bullets"
    if sheet_kind == "data" or (numeric_ratio_value >= 0.45 and row_count >= 3 and col_count >= 2):
        return "data_table", "generate_chart"
    if text_ratio >= 0.55 or (long_text_count >= 1 and numeric_ratio_value < 0.35):
        return "text_block", "summarize_to_bullets"
    if row_count <= 12 and col_count <= 6 and 0.25 <= numeric_ratio_value < 0.45 and text_ratio >= 0.25:
        return "metric_table", "create_kpi_cards"
    if row_count <= 12 and col_count <= 8:
        return "mixed_table", "insert_table"
    return "mixed_table", "manual_review_or_split"


def cell_block_stats(
    cells: dict[tuple[int, int], dict[str, Any]],
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
) -> dict[str, Any]:
    text_count = 0
    numeric_count = 0
    formula_count = 0
    long_text_count = 0
    non_empty = 0
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            item = cells.get((row, col))
            if not item:
                continue
            non_empty += 1
            if item.get("formula"):
                formula_count += 1
            if item["kind"] == "number":
                numeric_count += 1
            elif item["kind"] == "text":
                text_count += 1
                if len(str(item["value"]).strip()) >= 40:
                    long_text_count += 1
    blank_count = (max_row - min_row + 1) * (max_col - min_col + 1) - non_empty
    text_ratio = round(text_count / non_empty, 3) if non_empty else 0.0
    numeric_ratio_value = round(numeric_count / non_empty, 3) if non_empty else 0.0
    return {
        "rowCount": max_row - min_row + 1,
        "colCount": max_col - min_col + 1,
        "nonEmptyCellCount": non_empty,
        "blankCellCount": blank_count,
        "textCellCount": text_count,
        "numericCellCount": numeric_count,
        "formulaCellCount": formula_count,
        "longTextCellCount": long_text_count,
        "textCellRatio": text_ratio,
        "numericCellRatio": numeric_ratio_value,
    }


def text_from_rows(rows: list[list[Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        row_text = " ".join(str(value).strip() for value in row if str(value).strip())
        if row_text:
            parts.append(row_text)
    return "\n".join(parts)


def row_text(row: list[Any]) -> str:
    return " ".join(str(value).strip() for value in row if str(value).strip())


def is_caption_text(text: str) -> bool:
    return bool(re.match(r"^图\s*[：:]", text.strip()))


def caption_rows_from_rows(
    rows: list[list[Any]],
    min_row: int,
    min_col: int,
    max_col: int,
) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    for offset, row in enumerate(rows):
        text = row_text(row)
        if not is_caption_text(text):
            continue
        excel_row = min_row + offset
        captions.append(
            {
                "range": range_ref(excel_row, min_col, excel_row, max_col),
                "text": text,
            }
        )
    return captions


def compact_blank_columns(rows: list[list[Any]]) -> tuple[list[list[Any]], list[int]]:
    if not rows:
        return rows, []
    max_cols = max(len(row) for row in rows)
    keep_indices: list[int] = []
    removed_columns: list[int] = []
    for idx in range(max_cols):
        has_value = any(idx < len(row) and str(row[idx]).strip() for row in rows)
        if has_value:
            keep_indices.append(idx)
        else:
            removed_columns.append(idx + 1)
    if not removed_columns:
        return rows, []
    compacted = [
        [row[idx] if idx < len(row) else "" for idx in keep_indices]
        for row in rows
    ]
    return compacted, removed_columns


def write_table_workbook(path: Path, rows: list[list[Any]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "table"
    for row in rows:
        worksheet.append(row)

    for column_cells in worksheet.columns:
        values = [str(cell.value) for cell in column_cells if cell.value not in (None, "")]
        width = min(36, max(10, max((len(value) for value in values), default=8) + 2))
        worksheet.column_dimensions[column_cells[0].column_letter].width = width
    workbook.save(path)


def cell_blocks_for_sheet(
    cells: dict[tuple[int, int], dict[str, Any]],
    occupied_positions: set[tuple[int, int]],
    max_sample_rows: int,
    *,
    sheet_name: str,
    sheet_kind: str,
    tables_dir: Path,
    table_assets_dir: Path,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    sheet_slug = safe_name(sheet_name, "sheet")
    block_index = 0
    for min_row, max_row, min_col, max_col in detect_rect_blocks(cells, occupied_positions):
        row_count = max_row - min_row + 1
        col_count = max_col - min_col + 1
        non_empty = sum(1 for (r, c) in cells if min_row <= r <= max_row and min_col <= c <= max_col)
        if non_empty < 1:
            continue
        block_index += 1
        stats = cell_block_stats(cells, min_row, max_row, min_col, max_col)
        block_type, action = classify_cell_block(stats, sheet_kind)
        size_class = "small" if row_count <= 12 and col_count <= 8 else "large"
        all_rows = [
            row_values(cells, row, min_col, max_col)
            for row in range(min_row, max_row + 1)
        ]
        caption_rows = caption_rows_from_rows(all_rows, min_row, min_col, max_col)
        export_rows, removed_blank_columns = compact_blank_columns(all_rows)
        sample_rows = export_rows[:max_sample_rows]
        table_name = f"{sheet_slug}_block_{block_index:02d}.csv"
        table_path = tables_dir / table_name
        with table_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows(export_rows)
        text = text_from_rows(all_rows) if block_type == "text_block" else ""
        block: dict[str, Any] = {
            "blockId": f"{sheet_slug}_block_{block_index:02d}",
            "range": range_ref(min_row, min_col, max_row, max_col),
            "blockType": block_type,
            "dataPath": str(table_path),
            "relativeDataPath": f"tables/{table_name}",
            "fullDataIncluded": False,
            **stats,
            "sizeClass": size_class,
            "recommendedAction": action,
            "sampleRows": sample_rows,
            "text": text,
            "captionRows": caption_rows,
            "captionText": "\n".join(caption["text"] for caption in caption_rows),
            "exportedColCount": len(export_rows[0]) if export_rows else 0,
            "removedBlankColumns": removed_blank_columns,
        }
        if block_type in {"data_table", "mixed_table", "metric_table"}:
            xlsx_name = f"{sheet_slug}_block_{block_index:02d}.xlsx"
            xlsx_path = table_assets_dir / xlsx_name
            write_table_workbook(xlsx_path, export_rows)
            block["tableWorkbookPath"] = str(xlsx_path)
            block["relativeTableWorkbookPath"] = f"table-assets/{xlsx_name}"
        blocks.append(block)
    return blocks


def text_notes_from_blocks(cell_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for block in cell_blocks:
        if block["blockType"] != "text_block":
            continue
        role = "title" if block["range"].startswith("A1") else "insight"
        text = block.get("text", "")
        if any(token in text for token in ["注", "备注", "数据来源", "单位"]):
            role = "footnote"
        notes.append(
            {
                "range": block["range"],
                "role": role,
                "text": text,
                "sourceBlockId": block["blockId"],
                "recommendedUse": block["recommendedAction"],
            }
        )
    return notes


def metric_assets_from_blocks(cell_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: block[key]
            for key in [
                "blockId",
                "range",
                "dataPath",
                "relativeDataPath",
                "rowCount",
                "colCount",
                "textCellRatio",
                "numericCellRatio",
                "recommendedAction",
                "sampleRows",
            ]
            if key in block
        }
        for block in cell_blocks
        if block["blockType"] == "metric_table"
    ]


def table_assets_from_blocks(cell_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in block.items() if key != "text"}
        for block in cell_blocks
        if block["blockType"] in {"data_table", "mixed_table"}
    ]


def text_notes_for_sheet(cells: dict[tuple[int, int], dict[str, Any]], sheet_kind: str) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not cells:
        return notes
    rows = sorted({r for r, _c in cells})
    for row in rows:
        text_items = []
        numeric_count = 0
        min_col = 10**9
        max_col = 0
        for (r, col), item in cells.items():
            if r != row:
                continue
            min_col = min(min_col, col)
            max_col = max(max_col, col)
            if item["kind"] == "number":
                numeric_count += 1
            elif item["kind"] == "text":
                value = str(item["value"]).strip()
                if value:
                    text_items.append(value)
        if not text_items:
            continue
        text = " ".join(text_items)
        if len(text) < 2:
            continue
        if numeric_count > len(text_items) and sheet_kind != "metadata":
            continue
        if re.fullmatch(r"[\d\s.,:%+-]+", text):
            continue
        role = "insight"
        recommended = "summarize_to_bullets"
        if row <= 3:
            role = "title"
            recommended = "slide_title"
        if any(token in text for token in ["注", "备注", "数据来源", "单位"]):
            role = "footnote"
            recommended = "caption_or_footnote"
        notes.append(
            {
                "range": range_ref(row, min_col, row, max_col),
                "role": role,
                "text": text,
                "recommendedUse": recommended,
            }
        )
    return notes[:40]


def anchor_cell(pos: ET.Element | None) -> str:
    if pos is None:
        return "?"
    row = pos.find("xdr:row", NS)
    col = pos.find("xdr:col", NS)
    if row is None or col is None:
        return "?"
    return cell_ref(int(row.text or "0") + 1, int(col.text or "0") + 1)


def parse_cell_range(value: str) -> tuple[int, int, int, int] | None:
    if not value or value == "?":
        return None
    try:
        if ":" in value:
            start, end = value.split(":", 1)
        else:
            start = end = value
        min_row, min_col = split_cell_ref(start)
        max_row, max_col = split_cell_ref(end)
    except Exception:
        return None
    return min(min_row, max_row), min(min_col, max_col), max(min_row, max_row), max(min_col, max_col)


def image_anchor_ranges(image_assets: list[dict[str, Any]]) -> list[tuple[int, int, int, int]]:
    ranges: list[tuple[int, int, int, int]] = []
    for image in image_assets:
        parsed = parse_cell_range(image.get("anchor", ""))
        if parsed:
            ranges.append(parsed)
    return ranges


def ranges_touch_or_near(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
    *,
    row_margin: int = 1,
    col_margin: int = 1,
) -> bool:
    l_min_row, l_min_col, l_max_row, l_max_col = left
    r_min_row, r_min_col, r_max_row, r_max_col = right
    return not (
        l_max_row + row_margin < r_min_row
        or r_max_row + row_margin < l_min_row
        or l_max_col + col_margin < r_min_col
        or r_max_col + col_margin < l_min_col
    )


def media_extension(media_part: str, blob: bytes) -> str:
    suffix = Path(media_part).suffix
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(mimetypes.guess_type(media_part)[0] or "")
    return guessed or ".bin"


def extract_image_assets(
    zf: zipfile.ZipFile,
    sheet_name: str,
    drawing_path: str | None,
    picture_assets_dir: Path,
) -> list[dict[str, Any]]:
    if not drawing_path:
        return []
    try:
        root = read_xml(zf, drawing_path)
    except KeyError:
        return []
    rels = relationships(zf, drawing_path)
    anchors = (
        root.findall("xdr:twoCellAnchor", NS)
        + root.findall("xdr:oneCellAnchor", NS)
        + root.findall("xdr:absoluteAnchor", NS)
    )
    images: list[dict[str, Any]] = []
    sheet_slug = safe_name(sheet_name, "sheet")
    for index, anchor in enumerate(anchors, start=1):
        pic = anchor.find("xdr:pic", NS)
        if pic is None:
            continue
        blip = pic.find(".//a:blip", NS)
        rel_id = None
        if blip is not None:
            rel_id = blip.attrib.get(f"{{{NS['r']}}}embed") or blip.attrib.get(f"{{{NS['r']}}}link")
        if not rel_id or rel_id not in rels:
            continue
        media_part = normalize_part_path(drawing_path, rels[rel_id]["target"])
        try:
            blob = zf.read(media_part)
        except KeyError:
            continue
        name_node = pic.find(".//xdr:cNvPr", NS)
        shape_name = name_node.attrib.get("name", f"image_{index}") if name_node is not None else f"image_{index}"
        ext = media_extension(media_part, blob)
        output_name = f"{sheet_slug}_image_{index:02d}{ext}"
        output_path = picture_assets_dir / output_name
        output_path.write_bytes(blob)
        frm = anchor.find("xdr:from", NS)
        to = anchor.find("xdr:to", NS)
        anchor_text = f"{anchor_cell(frm)}:{anchor_cell(to)}" if to is not None else anchor_cell(frm)
        images.append(
            {
                "imageId": f"{sheet_slug}_image_{index:02d}",
                "name": shape_name,
                "path": str(output_path),
                "relativePath": f"picture-assets/{output_name}",
                "sourcePart": media_part,
                "anchor": anchor_text,
                "mediaType": mimetypes.guess_type(output_name)[0] or "application/octet-stream",
                "recommendedAction": "insert_image",
            }
        )
    return images


def add_nearby_text_once(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    key = (item.get("sourceBlockId"), item.get("range"), item.get("text"))
    for existing in items:
        existing_key = (
            existing.get("sourceBlockId"),
            existing.get("range"),
            existing.get("text"),
        )
        if existing_key == key:
            return
    items.append(item)


def caption_side_and_distance(
    caption_range: tuple[int, int, int, int],
    image_range: tuple[int, int, int, int],
) -> tuple[str, int]:
    cap_min_row, _cap_min_col, cap_max_row, _cap_max_col = caption_range
    img_min_row, _img_min_col, img_max_row, _img_max_col = image_range
    if cap_max_row < img_min_row:
        return "above", img_min_row - cap_max_row
    if cap_min_row > img_max_row:
        return "below", cap_min_row - img_max_row
    return "overlap", 0


def caption_rows_for_image(
    caption_rows: list[dict[str, Any]],
    image_range: tuple[int, int, int, int],
) -> list[dict[str, Any]]:
    candidates: list[tuple[str, int, dict[str, Any]]] = []
    for caption in caption_rows:
        caption_range = parse_cell_range(caption.get("range", ""))
        if not caption_range:
            continue
        if not ranges_touch_or_near(caption_range, image_range, row_margin=1, col_margin=2):
            continue
        side, distance = caption_side_and_distance(caption_range, image_range)
        candidates.append((side, distance, caption))
    for side in ["above", "overlap", "below"]:
        side_candidates = [item for item in candidates if item[0] == side]
        if side_candidates:
            min_distance = min(item[1] for item in side_candidates)
            return [item[2] for item in side_candidates if item[1] == min_distance]
    return []


def enrich_images_with_nearby_text(
    image_assets: list[dict[str, Any]],
    cell_blocks: list[dict[str, Any]],
) -> None:
    for image in image_assets:
        image_range = parse_cell_range(image.get("anchor", ""))
        if not image_range:
            continue
        nearby_texts: list[dict[str, Any]] = []
        related_blocks: list[dict[str, Any]] = []
        for block in cell_blocks:
            block_range = parse_cell_range(block.get("range", ""))
            if not block_range:
                continue
            if not ranges_touch_or_near(block_range, image_range, row_margin=2, col_margin=2):
                continue
            related_blocks.append(
                {
                    "blockId": block["blockId"],
                    "range": block["range"],
                    "blockType": block["blockType"],
                    "recommendedAction": block["recommendedAction"],
                }
            )
            block.setdefault("associatedImageIds", []).append(image["imageId"])
            if block["blockType"] == "text_block" and block.get("text"):
                add_nearby_text_once(
                    nearby_texts,
                    {
                        "sourceBlockId": block["blockId"],
                        "range": block["range"],
                        "text": block["text"],
                    }
                )
                block["recommendedAction"] = "image_caption_or_context"
            for caption in caption_rows_for_image(block.get("captionRows", []), image_range):
                add_nearby_text_once(
                    nearby_texts,
                    {
                        "sourceBlockId": block["blockId"],
                        "range": caption["range"],
                        "text": caption["text"],
                        "sourceType": "caption_row",
                    },
                )
        if nearby_texts:
            image["nearbyText"] = "\n".join(item["text"] for item in nearby_texts)
            image["nearbyTextBlocks"] = nearby_texts
        if related_blocks:
            image["relatedCellBlocks"] = related_blocks


def drawing_path_for_sheet(zf: zipfile.ZipFile, sheet_path: str, sheet_root: ET.Element) -> str | None:
    drawing = sheet_root.find("main:drawing", NS)
    if drawing is None:
        return None
    rel_id = drawing.attrib.get(f"{{{NS['r']}}}id")
    if not rel_id:
        return None
    rels = relationships(zf, sheet_path)
    if rel_id not in rels:
        return None
    return normalize_part_path(sheet_path, rels[rel_id]["target"])


def recommended_slide_plan(group: dict[str, Any]) -> list[str]:
    plans: list[str] = []
    if group["kind"] == "metadata":
        return ["cover"]
    if group["kind"] == "data":
        return ["support_data_for_chart_renderer"]
    if group["imageAssets"] and group["textNotes"]:
        plans.append("content_visual_with_bullets")
    if group["imageAssets"] and not group["textNotes"]:
        plans.append("content_single_visual")
    for table in group["tableAssets"]:
        if table["recommendedAction"] == "generate_chart":
            plans.append("content_generated_chart")
            break
    if any(table["recommendedAction"] == "insert_table" for table in group["tableAssets"]):
        plans.append("content_table")
    if group["textNotes"] and not plans:
        plans.append("content_text_bullets")
    return plans or ["manual_review"]


def compact_text(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def infer_group_title(sheet_name: str, text_notes: list[dict[str, Any]]) -> str:
    return sheet_name


def table_description(table: dict[str, Any]) -> str:
    rows = table.get("rowCount", 0)
    cols = table.get("colCount", 0)
    kind = table.get("blockType", "table")
    action = table.get("recommendedAction", "")
    return f"{kind}, {rows}行 x {cols}列, 建议: {action}"


def table_text_preview(table: dict[str, Any], limit: int = 180) -> str:
    parts: list[str] = []
    for row in table.get("sampleRows", []):
        for cell in row:
            text = str(cell).strip()
            if text and not re.fullmatch(r"[\d\s.,:%+-]+", text):
                parts.append(text)
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return compact_text(" | ".join(seen), limit)


def table_title(table: dict[str, Any]) -> str:
    for row in table.get("sampleRows", [])[:3]:
        texts = [str(cell).strip() for cell in row if str(cell).strip()]
        if len(texts) == 1 and not re.fullmatch(r"[\d\s.,:%+-]+", texts[0]):
            return compact_text(texts[0], 60)
    preview = table_text_preview(table, 60)
    return preview or table.get("blockId", "table")


def picture_description(picture: dict[str, Any]) -> str:
    nearby = compact_text(picture.get("nearbyText", ""), 120)
    if nearby:
        return nearby
    name = picture.get("name") or picture.get("imageId") or "picture"
    return f"{name}, 锚点 {picture.get('anchor', '')}"


def build_structured_content(
    sheet_name: str,
    text_notes: list[dict[str, Any]],
    table_assets: list[dict[str, Any]],
    image_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    title = infer_group_title(sheet_name, text_notes)
    text_items = [
        {
            "index": index,
            "role": note.get("role", "insight"),
            "range": note.get("range"),
            "sourceBlockId": note.get("sourceBlockId"),
            "text": note.get("text", ""),
            "summary": compact_text(note.get("text", "")),
        }
        for index, note in enumerate(text_notes, start=1)
    ]
    tables = [
        {
            "index": index,
            "sourceBlockId": table.get("blockId"),
            "range": table.get("range"),
            "rowCount": table.get("rowCount"),
            "colCount": table.get("colCount"),
            "blockType": table.get("blockType"),
            "title": table_title(table),
            "description": table_description(table),
            "captionText": table.get("captionText", ""),
            "captionRows": table.get("captionRows", []),
            "textPreview": table_text_preview(table),
            "relativeDataPath": table.get("relativeDataPath"),
            "relativeTableWorkbookPath": table.get("relativeTableWorkbookPath"),
        }
        for index, table in enumerate(table_assets, start=1)
    ]
    pictures = [
        {
            "index": index,
            "imageId": picture.get("imageId"),
            "name": picture.get("name"),
            "anchor": picture.get("anchor"),
            "description": picture_description(picture),
            "relativePath": picture.get("relativePath"),
            "nearbyText": picture.get("nearbyText", ""),
            "nearbyTextBlocks": picture.get("nearbyTextBlocks", []),
        }
        for index, picture in enumerate(image_assets, start=1)
    ]
    return {
        "title": title,
        "textContent": text_items,
        "tables": tables,
        "pictures": pictures,
    }


def build_manifest(workbook: Path, output_dir: Path, max_sample_rows: int) -> dict[str, Any]:
    picture_assets_dir = output_dir / "picture-assets"
    tables_dir = output_dir / "tables"
    table_assets_dir = output_dir / "table-assets"
    picture_assets_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    table_assets_dir.mkdir(parents=True, exist_ok=True)
    shared_strings: list[str]
    manifest_sheets: list[dict[str, Any]] = []
    content_groups: list[dict[str, Any]] = []
    deck_meta: dict[str, Any] = {}

    with zipfile.ZipFile(workbook) as zf:
        shared_strings = parse_shared_strings(zf)
        date_style_ids = parse_date_style_ids(zf)
        epoch = workbook_epoch(zf)
        workbook_part = "xl/workbook.xml"
        workbook_root = read_xml(zf, workbook_part)
        workbook_rels = relationships(zf, workbook_part)
        for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
            sheet_name = sheet.attrib["name"]
            rel_id = sheet.attrib[f"{{{NS['r']}}}id"]
            sheet_path = normalize_part_path(workbook_part, workbook_rels[rel_id]["target"])
            sheet_root = read_xml(zf, sheet_path)
            cells, row_numbers = parse_sheet_cells(sheet_root, shared_strings, date_style_ids, epoch)
            merged_ranges = parse_merged_ranges(sheet_root)
            kind = classify_sheet(sheet_name)
            dimension = sheet_dimension(sheet_root, cells)
            merge_count = len(merged_ranges)
            drawing_path = drawing_path_for_sheet(zf, sheet_path, sheet_root)
            image_assets = extract_image_assets(zf, sheet_name, drawing_path, picture_assets_dir)
            occupied_positions = occupied_positions_for_detection(
                cells,
                merged_ranges,
                image_anchor_ranges(image_assets),
            )
            cell_blocks = cell_blocks_for_sheet(
                cells,
                occupied_positions,
                max_sample_rows,
                sheet_name=sheet_name,
                sheet_kind=kind,
                tables_dir=tables_dir,
                table_assets_dir=table_assets_dir,
            )
            enrich_images_with_nearby_text(image_assets, cell_blocks)
            text_notes = text_notes_from_blocks(cell_blocks)
            metric_assets = metric_assets_from_blocks(cell_blocks)
            table_assets = table_assets_from_blocks(cell_blocks)
            if kind == "metadata":
                deck_meta.update(extract_deck_meta(sheet_name, cells))

            manifest_sheets.append(
                {
                    "name": sheet_name,
                    "kind": kind,
                    "sheetPath": sheet_path,
                    "dimension": dimension,
                    "rowCount": len(row_numbers),
                    "cellCount": len(cells),
                    "mergeCount": merge_count,
                    "drawingPath": drawing_path,
                    "imageCount": len(image_assets),
                    "tableBlockCount": len(table_assets),
                    "cellBlockCount": len(cell_blocks),
                    "metricBlockCount": len(metric_assets),
                    "textNoteCount": len(text_notes),
                }
            )
            group = {
                "groupId": safe_name(sheet_name, "sheet"),
                "sheet": sheet_name,
                "kind": kind,
                "title": infer_group_title(sheet_name, text_notes),
                "cellBlocks": cell_blocks,
                "textNotes": text_notes,
                "metricAssets": metric_assets,
                "tableAssets": table_assets,
                "imageAssets": image_assets,
            }
            group["structuredContent"] = build_structured_content(
                sheet_name,
                text_notes,
                table_assets,
                image_assets,
            )
            group["recommendedSlidePlan"] = recommended_slide_plan(group)
            content_groups.append(group)

    return {
        "version": 1,
        "sourceWorkbook": str(workbook),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "parser": {
            "name": "ppt-template-generator/excel_intake.py",
            "strategy": "xlsx-ooxml-mixed-content-v1",
        },
        "deckMeta": deck_meta,
        "pictureAssetsDir": str(picture_assets_dir),
        "tablesDir": str(tables_dir),
        "tableAssetsDir": str(table_assets_dir),
        "sheets": manifest_sheets,
        "contentGroups": content_groups,
    }


def print_summary(manifest: dict[str, Any]) -> None:
    print(f"Workbook: {manifest['sourceWorkbook']}")
    print(f"Sheets: {len(manifest['sheets'])}")
    print(f"Content groups: {len(manifest['contentGroups'])}")
    total_images = sum(sheet.get("imageCount", 0) for sheet in manifest["sheets"])
    total_blocks = sum(sheet.get("cellBlockCount", 0) for sheet in manifest["sheets"])
    total_tables = sum(sheet.get("tableBlockCount", 0) for sheet in manifest["sheets"])
    total_metrics = sum(sheet.get("metricBlockCount", 0) for sheet in manifest["sheets"])
    total_notes = sum(sheet.get("textNoteCount", 0) for sheet in manifest["sheets"])
    print(f"Images: {total_images}")
    print(f"Cell blocks: {total_blocks}")
    print(f"Table blocks: {total_tables}")
    print(f"Metric blocks: {total_metrics}")
    print(f"Text notes: {total_notes}")
    for sheet in manifest["sheets"]:
        print(
            f"- {sheet['name']} [{sheet['kind']}]: "
            f"{sheet['dimension']}, images={sheet['imageCount']}, "
            f"blocks={sheet['cellBlockCount']}, tables={sheet['tableBlockCount']}, "
            f"metrics={sheet['metricBlockCount']}, textNotes={sheet['textNoteCount']}"
        )


def main() -> int:
    args = parse_args()
    workbook = args.workbook.resolve()
    if not workbook.exists():
        print(f"Error: workbook not found: {workbook}", file=sys.stderr)
        return 1
    if workbook.suffix.lower() != ".xlsx":
        print(f"Error: expected .xlsx workbook: {workbook}", file=sys.stderr)
        return 1
    output_dir = (args.output_dir or workbook.with_name(f"{workbook.stem}_intake")).resolve()
    if output_dir.exists():
        # Keep reruns deterministic without removing user-edited manifests outside this folder.
        legacy_assets_dir = output_dir / "assets"
        picture_assets_dir = output_dir / "picture-assets"
        tables_dir = output_dir / "tables"
        table_assets_dir = output_dir / "table-assets"
        if legacy_assets_dir.exists():
            shutil.rmtree(legacy_assets_dir)
        if picture_assets_dir.exists():
            shutil.rmtree(picture_assets_dir)
        if tables_dir.exists():
            shutil.rmtree(tables_dir)
        if table_assets_dir.exists():
            shutil.rmtree(table_assets_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        manifest = build_manifest(workbook, output_dir, args.max_sample_rows)
        manifest_path = output_dir / "excel-content-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {manifest_path}")
    if args.pretty:
        print_summary(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
