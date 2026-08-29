from __future__ import annotations

import csv
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any


STYLE = {
    "font": "Microsoft YaHei",
    "background": "#FFFFFF",
    "text": "#111111",
    "muted": "#666666",
    "primary": "#9E0116",
    "primaryDark": "#6F0010",
    "accent": "#BF9D5A",
    "grid": "#D9D9D9",
    "lightFill": "#F6F6F6",
    "firstColumnFill": "#F3E6E8",
    "series": ["#9E0116", "#6F0010", "#7F7F7F", "#B0B0B0", "#BF9D5A", "#C9CDD4", "#333333"],
}


def setup_matplotlib() -> None:
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="ppt-skill-mpl-"))
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams

    candidates = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS", "DejaVu Sans"]
    available = {font.name for font in font_manager.fontManager.ttflist}
    chosen = next((font for font in candidates if font in available), "DejaVu Sans")
    rcParams["font.sans-serif"] = [chosen]
    rcParams["axes.unicode_minus"] = False


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [[str(cell).strip() for cell in row] for row in csv.reader(handle)]
    max_cols = max((len(row) for row in rows), default=0)
    return [row + [""] * (max_cols - len(row)) for row in rows]


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


def row_text(row: list[str]) -> str:
    return " ".join(cell.strip() for cell in row if cell.strip())


def compact_text(value: str, limit: int = 80) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "..."


def is_placeholder_label(value: Any) -> bool:
    text = compact_text(str(value or ""), 40).strip()
    if not text:
        return True
    return bool(
        re.match(r"^(series|column|col|row|r|c)\s*\d+$", text, flags=re.IGNORECASE)
        or re.match(r"^\u5217\s*\d+$", text)
        or re.match(r"^\u884c\s*\d+$", text)
    )


def clean_series_label(value: Any) -> str | None:
    text = compact_text(str(value or ""), 40).strip()
    return None if is_placeholder_label(text) else text


def wrap_text(value: Any, width: int = 12, max_lines: int = 3) -> str:
    text = str(value or "").strip()
    if len(text) <= width:
        return text
    lines = [text[idx : idx + width] for idx in range(0, len(text), width)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = compact_text(lines[-1], max(4, width))
    return "\n".join(lines)


def wrap_label(value: Any, width: int = 8) -> str:
    return wrap_text(value, width=width, max_lines=4)


def get_render_rows(plan: dict[str, Any], manifest_dir: Path) -> tuple[list[str], list[list[str]], list[list[str]]]:
    rows = read_csv_rows(manifest_dir / plan["relativeDataPath"])
    header_info = plan.get("cleaning", {}).get("header", {})
    header_idx = header_info.get("csvRowIndex")
    headers = header_info.get("headers") or []
    if header_idx is None or header_idx >= len(rows):
        header_idx = 0
        headers = rows[0] if rows else []
    data_start = plan.get("cleaning", {}).get("dataStartCsvRowIndex", header_idx + 1)
    data_rows: list[list[str]] = []
    for row in rows[data_start:]:
        text = row_text(row)
        if not text:
            continue
        if re.match(r"^图\s*[：:]", text):
            continue
        data_rows.append(row[: len(headers)])
    return headers, data_rows, rows


def title_for_plan(plan: dict[str, Any]) -> str:
    caption = compact_text(plan.get("captionText", "").splitlines()[0] if plan.get("captionText") else "", 70)
    return caption or compact_text(plan.get("assetId", "visual"), 70)


def numeric_column_indices(plan: dict[str, Any]) -> list[int]:
    return [col["index"] for col in plan.get("profile", {}).get("numericColumns", [])]


def valid_numeric_series(
    plan: dict[str, Any],
    headers: list[str],
    rows: list[list[str]],
    *,
    require_label: bool = True,
    min_values: int = 1,
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for col_idx in numeric_column_indices(plan):
        if col_idx == 0:
            continue
        raw_label = headers[col_idx] if col_idx < len(headers) else ""
        label = clean_series_label(raw_label)
        if require_label and not label:
            continue
        values: list[float | None] = []
        valid_count = 0
        for row in rows:
            number = parse_number(row[col_idx] if col_idx < len(row) else "")
            values.append(number)
            if number is not None and not math.isnan(number):
                valid_count += 1
        if valid_count >= min_values:
            series.append(
                {
                    "colIndex": col_idx,
                    "label": label or f"series {len(series) + 1}",
                    "values": values,
                    "validCount": valid_count,
                }
            )
    return series


def rows_with_chart_data(rows: list[list[str]], series: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    kept: list[tuple[int, list[str]]] = []
    for row_idx, row in enumerate(rows):
        label = clean_series_label(row[0] if row else "")
        if not label:
            continue
        has_number = any(item["values"][row_idx] is not None for item in series if row_idx < len(item["values"]))
        if has_number:
            kept.append((row_idx, row))
    return kept


def is_percent_like(headers: list[str], values: list[float]) -> bool:
    header_text = " ".join(headers)
    finite = [abs(value) for value in values if value is not None and not math.isnan(value)]
    if not finite:
        return False
    max_value = max(finite)
    percent_tokens = ["%", "率", "占比", "比例", "仓位", "贡献", "增长"]
    if any(token in header_text for token in percent_tokens):
        return max_value <= 2.0
    return max_value <= 1.0


def paged_rows(rows: list[list[str]], per_page: int) -> list[list[list[str]]]:
    if not rows:
        return [[]]
    return [rows[idx : idx + per_page] for idx in range(0, len(rows), per_page)]


def save_figure(fig: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=STYLE["background"])
    import matplotlib.pyplot as plt

    plt.close(fig)
