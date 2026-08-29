#!/usr/bin/env python3
"""Create an editable Step 2A visual-asset plan from an Excel intake manifest."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CATEGORY_KEYWORDS = [
    "行业",
    "资产",
    "基金",
    "名称",
    "品种",
    "类别",
    "评级",
    "久期",
    "分组",
    "板块",
    "组合",
    "产品",
]
NUMERIC_KEYWORDS = [
    "收益",
    "收益率",
    "占比",
    "比例",
    "金额",
    "规模",
    "市值",
    "仓位",
    "净值",
    "贡献",
    "利率",
    "久期",
    "ytm",
    "q1",
    "q2",
    "q3",
    "q4",
    "本月以来",
    "今年以来",
]
DATE_KEYWORDS = ["日期", "时间", "月份", "月度", "季度"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build visual-asset-plan.json for Step 2A review.")
    parser.add_argument("manifest", type=Path, help="Path to excel-content-manifest.json")
    parser.add_argument("--output", type=Path, help="Defaults to visual-asset-plan.json beside manifest")
    parser.add_argument("--pretty", action="store_true", help="Print compact summary")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def parse_range(value: str) -> tuple[int, int, int, int] | None:
    if not value or value == "?":
        return None
    try:
        start, end = value.split(":", 1) if ":" in value else (value, value)
        min_row, min_col = split_cell_ref(start)
        max_row, max_col = split_cell_ref(end)
    except Exception:
        return None
    return min(min_row, max_row), min(min_col, max_col), max(min_row, max_row), max(min_col, max_col)


def row_range(block_range: str, csv_row_index: int, width: int) -> str:
    parsed = parse_range(block_range)
    if not parsed:
        return ""
    min_row, min_col, _max_row, _max_col = parsed
    row = min_row + csv_row_index
    return f"{num_to_col(min_col)}{row}:{num_to_col(min_col + max(width - 1, 0))}{row}"


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [[str(cell).strip() for cell in row] for row in csv.reader(handle)]
    max_cols = max((len(row) for row in rows), default=0)
    return [row + [""] * (max_cols - len(row)) for row in rows]


def compact_text(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


CONTENT_STOPWORDS = {
    "组合",
    "资产",
    "情况",
    "回顾",
    "数据",
    "比例",
    "占比",
    "备注",
    "报告",
    "期间",
    "图",
    "表",
    "截至",
    "期初",
    "期末",
    "平均",
}


def content_terms(text: str) -> set[str]:
    normalized = re.sub(r"[\d\s,，.。:：;；%（）()【】\\/_\-—]+", " ", str(text or ""))
    raw_parts = [part.strip() for part in normalized.split() if part.strip()]
    terms: set[str] = set()
    for part in raw_parts:
        if len(part) < 2:
            continue
        if len(part) <= 8 and part not in CONTENT_STOPWORDS:
            terms.add(part)
        for size in (2, 3, 4):
            for idx in range(0, max(len(part) - size + 1, 0)):
                token = part[idx : idx + size]
                if token not in CONTENT_STOPWORDS:
                    terms.add(token)
    return terms


def table_content_text(table: dict[str, Any], headers: list[str], data_rows: list[dict[str, Any]]) -> str:
    samples: list[str] = []
    for row in data_rows[:12]:
        cells = row.get("cells", [])
        if cells:
            samples.append(str(cells[0]))
    return " ".join(
        [
            str(table.get("blockId", "")),
            str(table.get("captionText", "")),
            " ".join(headers),
            " ".join(samples),
        ]
    )


def content_match_score(table_text: str, image_text: str) -> dict[str, Any]:
    table_terms = content_terms(table_text)
    image_terms = content_terms(image_text)
    if not table_terms or not image_terms:
        return {
            "score": 0.0,
            "matchedTerms": [],
            "tableTermCount": len(table_terms),
            "imageTermCount": len(image_terms),
        }
    matched = sorted(table_terms & image_terms, key=lambda item: (-len(item), item))
    denominator = max(4, min(len(table_terms), len(image_terms)))
    score = min(1.0, len(matched) / denominator)
    return {
        "score": round(score, 3),
        "matchedTerms": matched[:12],
        "tableTermCount": len(table_terms),
        "imageTermCount": len(image_terms),
    }


def row_text(row: list[str]) -> str:
    return " ".join(cell.strip() for cell in row if cell.strip())


def parse_number(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"-", "--", "N/A", "nan", "None"}:
        return None
    text = text.replace(",", "").replace("，", "").replace("−", "-").replace("％", "%")
    percent = text.endswith("%")
    if percent:
        text = text[:-1]
    text = text.strip()
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100 if percent else number


def is_date(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
        return True
    if re.fullmatch(r"\d{8}", text):
        month = int(text[4:6])
        day = int(text[6:8])
        return 1 <= month <= 12 and 1 <= day <= 31
    return False


def is_caption(text: str) -> bool:
    return bool(re.match(r"^图\s*[：:]", text.strip()))


def is_blank_row(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def numeric_ratio(row: list[str]) -> float:
    values = [cell for cell in row if cell.strip()]
    if not values:
        return 0.0
    return sum(parse_number(cell) is not None for cell in values) / len(values)


def date_ratio(values: list[str]) -> float:
    non_empty = [value for value in values if str(value).strip()]
    if not non_empty:
        return 0.0
    return sum(is_date(value) for value in non_empty) / len(non_empty)


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def row_kind(row: list[str]) -> str:
    text = row_text(row)
    non_empty = [cell for cell in row if cell.strip()]
    if not non_empty:
        return "blank"
    if is_caption(text):
        return "caption"
    if len(non_empty) <= 2 and numeric_ratio(row) == 0:
        return "title"
    return "mixed"


def header_score(rows: list[list[str]], index: int) -> tuple[float, list[str]]:
    row = rows[index]
    non_empty = [cell for cell in row if cell.strip()]
    if len(non_empty) < 2:
        return -10.0, ["too_few_non_empty_cells"]
    text = row_text(row)
    if is_caption(text):
        return -10.0, ["caption_row"]

    reasons: list[str] = []
    score = 0.0
    row_num_ratio = numeric_ratio(row)
    label_ratio = 1.0 - row_num_ratio
    score += min(len(non_empty), 10) * 0.35
    score += label_ratio * 2.0
    if row_num_ratio <= 0.35:
        score += 1.0
        reasons.append("header_cells_are_mostly_labels")

    keyword_count = keyword_hits(text, DATE_KEYWORDS + CATEGORY_KEYWORDS + NUMERIC_KEYWORDS)
    if keyword_count:
        score += min(keyword_count, 5) * 0.9
        reasons.append("header_keywords_detected")

    next_rows = [r for r in rows[index + 1 : index + 6] if not is_blank_row(r) and not is_caption(row_text(r))]
    if next_rows:
        next_numeric = sum(numeric_ratio(r) for r in next_rows) / len(next_rows)
        if next_numeric > row_num_ratio + 0.2:
            score += 2.0
            reasons.append("following_rows_are_more_numeric")
        first_col_values = [r[0] if r else "" for r in next_rows]
        if date_ratio(first_col_values) >= 0.6:
            score += 1.6
            reasons.append("following_first_column_is_date_like")
        elif any(str(value).strip() and parse_number(value) is None for value in first_col_values):
            score += 0.8
            reasons.append("following_first_column_is_category_like")

    if index > 0 and row_kind(rows[index - 1]) in {"title", "caption", "blank"}:
        score += 0.4
        reasons.append("preceded_by_title_caption_or_blank")
    return score, reasons


def detect_header(rows: list[list[str]], block_range: str) -> dict[str, Any]:
    search_limit = min(len(rows), 25)
    candidates: list[dict[str, Any]] = []
    for idx in range(search_limit):
        score, reasons = header_score(rows, idx)
        if score > 0:
            candidates.append(
                {
                    "csvRowIndex": idx,
                    "excelRange": row_range(block_range, idx, len(rows[idx])),
                    "score": round(score, 3),
                    "reasons": reasons,
                    "cells": rows[idx],
                }
            )
    if not candidates:
        first_data = next((idx for idx, row in enumerate(rows) if not is_blank_row(row)), 0)
        width = len(rows[first_data]) if rows else 0
        return {
            "status": "not_found",
            "csvRowIndex": None,
            "excelRange": None,
            "confidence": 0.0,
            "headers": [f"列{idx + 1}" for idx in range(width)],
            "dataStartCsvRowIndex": first_data,
            "candidates": [],
        }
    best = max(candidates, key=lambda item: item["score"])
    headers = [cell.strip() or f"列{idx + 1}" for idx, cell in enumerate(best["cells"])]
    confidence = min(0.98, max(0.35, best["score"] / 8.0))
    return {
        "status": "found",
        "csvRowIndex": best["csvRowIndex"],
        "excelRange": best["excelRange"],
        "confidence": round(confidence, 3),
        "headers": headers,
        "dataStartCsvRowIndex": best["csvRowIndex"] + 1,
        "candidates": candidates[:6],
    }


def clean_data_rows(rows: list[list[str]], data_start: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[data_start:], start=data_start):
        text = row_text(row)
        kind = row_kind(row)
        if kind in {"blank", "caption", "title"}:
            continue
        result.append({"csvRowIndex": idx, "cells": row, "text": text})
    return result


def column_profile(headers: list[str], data_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    width = len(headers)
    for col_idx in range(width):
        values = [row["cells"][col_idx] if col_idx < len(row["cells"]) else "" for row in data_rows]
        non_empty = [value for value in values if str(value).strip()]
        numbers = [parse_number(value) for value in non_empty]
        numbers = [value for value in numbers if value is not None]
        dates = [value for value in non_empty if is_date(value)]
        numeric = len(numbers) / len(non_empty) if non_empty else 0.0
        date = len(dates) / len(non_empty) if non_empty else 0.0
        text_values = [str(value).strip() for value in non_empty if parse_number(value) is None and not is_date(value)]
        avg_text_len = sum(len(value) for value in text_values) / len(text_values) if text_values else 0
        profiles.append(
            {
                "index": col_idx,
                "name": headers[col_idx],
                "nonEmpty": len(non_empty),
                "numericRatio": round(numeric, 3),
                "dateRatio": round(date, 3),
                "isNumeric": numeric >= 0.55 and len(numbers) >= 2,
                "isDate": date >= 0.65 and len(dates) >= 2,
                "isCategory": numeric < 0.35 and date < 0.35 and len(text_values) >= 2,
                "averageTextLength": round(avg_text_len, 2),
                "sampleValues": non_empty[:5],
            }
        )
    return profiles


def related_images_for_block(group: dict[str, Any], block_id: str) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for image in group.get("imageAssets", []):
        for related_block in image.get("relatedCellBlocks", []):
            if related_block.get("blockId") == block_id:
                related.append(
                    {
                        "imageId": image.get("imageId"),
                        "anchor": image.get("anchor"),
                        "relativePath": image.get("relativePath"),
                        "nearbyText": image.get("nearbyText", ""),
                    }
                )
                break
    return related


def _range_metrics(a: tuple[int, int, int, int] | None, b: tuple[int, int, int, int] | None) -> dict[str, float]:
    if not a or not b:
        return {
            "rowOverlap": 0.0,
            "colOverlap": 0.0,
            "rowGap": 9999.0,
            "colGap": 9999.0,
            "overlapArea": 0.0,
        }
    a_r1, a_c1, a_r2, a_c2 = a
    b_r1, b_c1, b_r2, b_c2 = b
    row_overlap = max(0, min(a_r2, b_r2) - max(a_r1, b_r1) + 1)
    col_overlap = max(0, min(a_c2, b_c2) - max(a_c1, b_c1) + 1)
    row_gap = 0 if row_overlap else min(abs(a_r1 - b_r2), abs(b_r1 - a_r2))
    col_gap = 0 if col_overlap else min(abs(a_c1 - b_c2), abs(b_c1 - a_c2))
    return {
        "rowOverlap": float(row_overlap),
        "colOverlap": float(col_overlap),
        "rowGap": float(row_gap),
        "colGap": float(col_gap),
        "overlapArea": float(row_overlap * col_overlap),
    }


def score_source_image_matches(
    group: dict[str, Any],
    table: dict[str, Any],
    headers: list[str],
    data_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    table_range = parse_range(table.get("range", ""))
    block_id = table.get("blockId", "")
    table_text = table_content_text(table, headers, data_rows)
    candidates: list[dict[str, Any]] = []
    for image in group.get("imageAssets", []):
        image_range = parse_range(image.get("anchor", ""))
        exact_related = any(related_block.get("blockId") == block_id for related_block in image.get("relatedCellBlocks", []))
        metrics = _range_metrics(table_range, image_range)
        image_text = str(image.get("nearbyText", ""))
        content_match = content_match_score(table_text, image_text)
        reasons: list[str] = []
        score = 0.0
        if exact_related:
            score += 0.35
            reasons.append("exact_related_cell_block")
        if metrics["overlapArea"] > 0:
            score += 0.35
            reasons.append("image_anchor_overlaps_table_range")
        if metrics["rowOverlap"] > 0 and metrics["colGap"] <= 2:
            score += 0.15
            reasons.append("same_local_row_band")
        if metrics["colOverlap"] > 0 and metrics["rowGap"] <= 3:
            score += 0.15
            reasons.append("same_local_column_band")
        if metrics["rowGap"] <= 3 and metrics["colGap"] <= 2:
            score += 0.25
            reasons.append("same_local_diagonal_region")
        content_boost = min(0.2, content_match["score"] * 0.2)
        if content_boost:
            score += content_boost
            reasons.append("content_terms_overlap")
        if image.get("nearbyText"):
            score += 0.05
            reasons.append("image_has_caption_or_nearby_text")
        same_subsheet_region = bool(
            metrics["overlapArea"] > 0
            or (metrics["rowGap"] <= 3 and metrics["colOverlap"] > 0)
            or (metrics["colGap"] <= 2 and metrics["rowOverlap"] > 0)
            or (metrics["rowGap"] <= 3 and metrics["colGap"] <= 2)
        )
        candidates.append(
            {
                "imageId": image.get("imageId"),
                "anchor": image.get("anchor"),
                "relativePath": image.get("relativePath"),
                "nearbyText": image.get("nearbyText", ""),
                "score": round(min(score, 1.0), 3),
                "sameSubsheetRegion": same_subsheet_region,
                "contentMatch": content_match,
                "metrics": metrics,
                "reasons": reasons,
            }
        )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def qualified_source_images(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qualified: list[dict[str, Any]] = []
    for match in matches:
        if not match.get("sameSubsheetRegion") or match.get("score", 0) < 0.65:
            continue
        metrics = match.get("metrics", {})
        content_score = match.get("contentMatch", {}).get("score", 0)
        strong_geometry = metrics.get("overlapArea", 0) > 0 or (
            metrics.get("rowOverlap", 0) > 0 and metrics.get("colGap", 9999) <= 2
        ) or (
            metrics.get("colOverlap", 0) > 0 and metrics.get("rowGap", 9999) <= 3
        )
        if strong_geometry or content_score >= 0.08 or match.get("score", 0) >= 0.78:
            qualified.append(match)
    return qualified


def is_small_table_route(data_rows: list[dict[str, Any]], headers: list[str], columns: list[dict[str, Any]]) -> bool:
    return len(data_rows) <= 8 and len(headers) <= 8


def choose_table_route_and_class(
    headers: list[str],
    data_rows: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    table: dict[str, Any],
    related_images: list[dict[str, Any]],
) -> tuple[str, str | None, str, float, list[str]]:
    reasons: list[str] = []
    data_count = len(data_rows)
    numeric_cols = [col for col in columns if col["isNumeric"]]
    if related_images:
        best = related_images[0]
        reasons.append("source_image_match: qualified related Excel image exists")
        reasons.append("source_image_match: same local sheet region")
        reasons.extend(f"source_image_match: {reason}" for reason in best.get("reasons", []))
        return "source_image_route", None, "source_image", 0.92, reasons
    if is_small_table_route(data_rows, headers, columns):
        reasons.append("small_table_direct_render")
        reasons.append("small_table_rule: data rows <= 8 and columns <= 8")
        return "small_table_route", None, "styled_table_image", 0.82, reasons

    if not data_rows or not numeric_cols:
        return "chart_route", "table_like_or_other", "styled_table_image", 0.55, ["no_clear_numeric_data"]

    first_col = columns[0] if columns else {}
    header_text = " ".join(headers).lower()
    caption_text = str(table.get("captionText", "")).lower()
    combined_text = f"{header_text} {caption_text}"
    first_name = str(first_col.get("name", ""))
    first_name_lower = first_name.lower()

    first_col_name_is_date = keyword_hits(first_name_lower, DATE_KEYWORDS) > 0
    enough_time_points = data_count >= 6
    if first_col.get("isDate") and numeric_cols and (first_col_name_is_date or (first_col.get("dateRatio", 0) >= 0.9 and enough_time_points)):
        reasons.append("chart_route")
        reasons.append("trend: first_column_is_date_like")
        reasons.append("trend: numeric_series_columns_detected")
        confidence = 0.9 if len(numeric_cols) >= 2 else 0.82
        return "chart_route", "trend_chart", "trend_chart", confidence, reasons

    composition_keywords = ["配置", "占比", "分布", "结构", "仓位", "市值范围", "信用等级", "久期", "持仓比例", "相对占比"]
    if keyword_hits(combined_text, composition_keywords) >= 1 and numeric_cols:
        reasons.append("chart_route")
        reasons.append("composition: structure_distribution_or_share_keywords")
        return "chart_route", "composition_chart", "composition_chart", 0.82, reasons

    category_signal = first_col.get("isCategory") or keyword_hits(first_name, CATEGORY_KEYWORDS) > 0
    if category_signal and numeric_cols:
        reasons.append("chart_route")
        reasons.append("category: first_column_is_category_like")
        reasons.append("category: numeric_value_columns_detected")
        return "chart_route", "category_chart", "category_chart", 0.8, reasons

    reasons.append("chart_route")
    reasons.append("table_like_or_other: unclear_large_or_mixed_table")
    return "chart_route", "table_like_or_other", "styled_table_image", 0.62, reasons


def style_source_for_plan(visual_type: str, related_images: list[dict[str, Any]]) -> dict[str, Any]:
    if visual_type == "source_image":
        return {
            "primary": "related_source_image",
            "fallback": "ppt_template_default",
            "references": related_images,
        }
    if visual_type == "styled_table_image":
        if related_images:
            return {
                "primary": "image_asset_style",
                "fallback": "ppt_template_default",
                "references": related_images,
                "notes": "Fallback table rendering should still echo nearby image style when available.",
            }
        return {
            "primary": "excel_table_style_or_ppt_default",
            "fallback": "ppt_template_default",
            "references": [],
        }
    if related_images:
        return {
            "primary": "image_asset_style",
            "fallback": "ppt_template_default",
            "references": related_images,
        }
    return {
        "primary": "ppt_template_default",
        "fallback": "built_in_fund_report_default",
        "references": [],
    }


def pagination_policy(visual_type: str, data_rows: int) -> dict[str, Any]:
    if visual_type == "trend_chart":
        return {
            "dataPolicy": "use_all_rows",
            "axisPolicy": "thin_x_axis_tick_labels_if_needed",
            "maxRowsPerVisual": None,
        }
    if visual_type in {"category_chart", "composition_chart"}:
        if data_rows > 20:
            return {
                "dataPolicy": "paginate_without_dropping_rows",
                "rowsPerPage": 20,
                "pageCount": math.ceil(data_rows / 20),
            }
        return {"dataPolicy": "use_all_rows", "rowsPerPage": data_rows, "pageCount": 1}
    if data_rows > 24:
        return {
            "dataPolicy": "paginate_table_image_without_dropping_rows",
            "rowsPerPage": 24,
            "pageCount": math.ceil(data_rows / 24),
        }
    return {"dataPolicy": "use_all_rows", "rowsPerPage": data_rows, "pageCount": 1}


def plan_table_asset(manifest_dir: Path, group: dict[str, Any], table: dict[str, Any]) -> dict[str, Any]:
    data_path = manifest_dir / table.get("relativeDataPath", "")
    rows = read_csv_rows(data_path) if data_path.exists() else []
    header = detect_header(rows, table.get("range", ""))
    data_start = header.get("dataStartCsvRowIndex") or 0
    data_rows = clean_data_rows(rows, data_start)
    headers = header["headers"]
    columns = column_profile(headers, data_rows)
    source_image_matches = score_source_image_matches(group, table, headers, data_rows)
    related_images = qualified_source_images(source_image_matches)
    route, chart_class, visual_type, confidence, reasons = choose_table_route_and_class(headers, data_rows, columns, table, related_images)
    numeric_columns = [col for col in columns if col["isNumeric"]]
    date_columns = [col for col in columns if col["isDate"]]
    category_columns = [col for col in columns if col["isCategory"]]
    first_column = columns[0] if columns else None
    excluded_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        kind = row_kind(row)
        if kind in {"blank", "caption", "title"} and idx < data_start:
            excluded_rows.append(
                {
                    "csvRowIndex": idx,
                    "excelRange": row_range(table.get("range", ""), idx, len(row)),
                    "kind": kind,
                    "text": row_text(row),
                }
            )
    return {
        "assetId": table.get("blockId"),
        "assetKind": "table_asset",
        "sourceGroupId": group.get("groupId"),
        "sourceSheet": group.get("sheet"),
        "sourceRange": table.get("range"),
        "relativeDataPath": table.get("relativeDataPath"),
        "relativeTableWorkbookPath": table.get("relativeTableWorkbookPath"),
        "captionText": table.get("captionText", ""),
        "captionRows": table.get("captionRows", []),
        "relatedImages": related_images,
        "sourceImageCandidates": source_image_matches[:5],
        "cleaning": {
            "header": header,
            "excludedRowsBeforeData": excluded_rows,
            "dataStartCsvRowIndex": data_start,
            "dataRowCount": len(data_rows),
            "dataColumnCount": len(headers),
            "fullDataPreservedIn": table.get("relativeDataPath"),
        },
        "profile": {
            "firstColumn": first_column,
            "dateColumns": date_columns,
            "categoryColumns": category_columns,
            "numericColumns": numeric_columns,
            "columnProfiles": columns,
            "rowCount": table.get("rowCount"),
            "colCount": table.get("colCount"),
            "sourceBlockType": table.get("blockType"),
        },
        "recommendedVisual": {
            "route": route,
            "chartClass": chart_class,
            "visualType": visual_type,
            "confidence": round(confidence * min(1.0, max(header.get("confidence", 0.4), 0.4) / 0.7), 3),
            "reasons": reasons,
            "renderEngine": "python_renderer_later",
            "fallback": "styled_table_image",
            "pagination": pagination_policy(visual_type, len(data_rows)),
        },
        "styleSource": style_source_for_plan(visual_type, related_images),
        "manualOverride": None,
    }


def plan_image_asset(group: dict[str, Any], image: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetId": image.get("imageId"),
        "assetKind": "image_asset",
        "sourceGroupId": group.get("groupId"),
        "sourceSheet": group.get("sheet"),
        "anchor": image.get("anchor"),
        "relativePath": image.get("relativePath"),
        "captionText": image.get("nearbyText", ""),
        "nearbyTextBlocks": image.get("nearbyTextBlocks", []),
        "relatedCellBlocks": image.get("relatedCellBlocks", []),
        "recommendedVisual": {
            "visualType": "source_image",
            "confidence": 0.95,
            "renderEngine": "reuse_original_image",
            "reasons": ["excel_floating_image_preserved"],
        },
        "styleSource": {
            "primary": "source_image_itself",
            "fallback": "ppt_template_default",
            "references": [image.get("relativePath")],
        },
        "manualOverride": None,
    }


def build_plan(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_dir = manifest_path.parent
    table_plans: list[dict[str, Any]] = []
    image_plans: list[dict[str, Any]] = []
    for group in manifest.get("contentGroups", []):
        for table in group.get("tableAssets", []):
            table_plans.append(plan_table_asset(manifest_dir, group, table))
        for image in group.get("imageAssets", []):
            image_plans.append(plan_image_asset(group, image))

    visual_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    chart_class_counts: dict[str, int] = {}
    for plan in table_plans + image_plans:
        visual_type = plan["recommendedVisual"]["visualType"]
        visual_counts[visual_type] = visual_counts.get(visual_type, 0) + 1
        route = plan["recommendedVisual"].get("route")
        if route:
            route_counts[route] = route_counts.get(route, 0) + 1
        chart_class = plan["recommendedVisual"].get("chartClass")
        if chart_class:
            chart_class_counts[chart_class] = chart_class_counts.get(chart_class, 0) + 1

    return {
        "version": 1,
        "generatedAt": now_iso(),
        "sourceManifest": str(manifest_path),
        "planner": {
            "name": "visual_asset_planner",
            "step": "2A",
            "purpose": "Clean table assets, detect headers, recommend visual types, and choose style sources without rendering images.",
        },
        "styleProfile": {
            "chartStylePriority": ["image_asset_style", "ppt_template_default", "built_in_fund_report_default"],
            "tableStylePriority": ["excel_table_style_or_ppt_default", "image_asset_style", "ppt_template_default"],
            "defaultStyle": {
                "fontFamily": "Microsoft YaHei",
                "background": "#FFFFFF",
                "primaryRed": "#9E0116",
                "accentGold": "#BF9D5A",
                "gridGray": "#D9D9D9",
                "text": "#111111",
                "mutedText": "#666666",
            },
        },
        "summary": {
            "tablePlanCount": len(table_plans),
            "imagePlanCount": len(image_plans),
            "visualTypeCounts": visual_counts,
            "routeCounts": route_counts,
            "chartClassCounts": chart_class_counts,
            "needsRenderingCount": sum(
                1
                for plan in table_plans
                if plan["recommendedVisual"]["visualType"] != "source_image"
            ),
        },
        "tableVisualPlans": table_plans,
        "imageVisualPlans": image_plans,
    }


def main() -> int:
    args = parse_args()
    output = args.output or (args.manifest.parent / "visual-asset-plan.json")
    plan = build_plan(args.manifest)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.pretty:
        print(f"Wrote {output}")
        print(json.dumps(plan["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
