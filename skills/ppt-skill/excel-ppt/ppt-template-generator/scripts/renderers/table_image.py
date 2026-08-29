from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    STYLE,
    compact_text,
    get_render_rows,
    is_placeholder_label,
    paged_rows,
    parse_number,
    save_figure,
    setup_matplotlib,
    title_for_plan,
    wrap_text,
)


def _numeric_cell_count(row: list[Any]) -> int:
    return sum(1 for cell in row if parse_number(cell) is not None)


def _hierarchical_header_label(parent: str, child: str) -> str:
    short_parent = parent.replace("产品各类", "").replace("配置比例(%)", "配置比例(%)").strip()
    return f"{child}\n{short_parent}" if short_parent and short_parent != child else child


def _normalize_hierarchical_headers(headers: list[str], data_rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if not data_rows:
        return headers, data_rows

    subheader = data_rows[0]
    next_row = data_rows[1] if len(data_rows) > 1 else []
    subheader_text_cols = [
        idx
        for idx, cell in enumerate(subheader[: len(headers)])
        if str(cell or "").strip() and parse_number(cell) is None
    ]
    if len(subheader_text_cols) < 2:
        return headers, data_rows
    if _numeric_cell_count(subheader) > 0 or _numeric_cell_count(next_row) == 0:
        return headers, data_rows
    if not any(is_placeholder_label(headers[idx] if idx < len(headers) else "") for idx in subheader_text_cols):
        return headers, data_rows

    normalized = list(headers)
    current_parent = ""
    for idx in range(len(headers)):
        raw_header = str(headers[idx] or "").strip()
        if raw_header and not is_placeholder_label(raw_header):
            current_parent = raw_header
        child = str(subheader[idx] if idx < len(subheader) else "").strip()
        if not child:
            continue
        if current_parent and current_parent != child:
            normalized[idx] = _hierarchical_header_label(current_parent, child)
        else:
            normalized[idx] = child
    return normalized, data_rows[1:]


def format_table_cell(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("%"):
        number = parse_number(text)
        return text if number is None else f"{number * 100:.4f}%"
    number = parse_number(text)
    if number is None:
        return text
    if abs(number - round(number)) < 1e-12:
        return str(int(round(number)))
    return f"{number:.4f}"


def render_table_image(plan: dict[str, Any], manifest_dir: Path, output_base: Path) -> list[dict[str, Any]]:
    setup_matplotlib()
    import matplotlib.pyplot as plt

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    if not headers:
        headers = ["内容"]
    headers, data_rows = _normalize_hierarchical_headers(headers, data_rows)
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 24)
    pages = paged_rows(data_rows, per_page)
    outputs: list[dict[str, Any]] = []
    col_count = max(len(headers), 1)
    for page_idx, page_rows in enumerate(pages, start=1):
        path = output_base if len(pages) == 1 else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        first_col_width = 8 if col_count >= 6 else 10
        body_col_width = 9 if col_count >= 7 else 12
        visible_rows = [
            [
                wrap_text(
                    format_table_cell(cell),
                    width=first_col_width if col_idx == 0 else body_col_width,
                    max_lines=4 if col_idx == 0 else 3,
                )
                for col_idx, cell in enumerate(row[:col_count])
            ]
            for row in page_rows
        ]
        header_labels = [
            wrap_text(compact_text(header, 30), width=first_col_width if idx == 0 else body_col_width, max_lines=3)
            for idx, header in enumerate(headers)
        ]
        fig_height = max(2.8, min(12, 1.15 + 0.48 * (len(visible_rows) + 1)))
        fig_width = max(9.5, min(20, 1.8 * col_count))
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis("off")
        if plan.get("captionText"):
            ax.set_title(compact_text(plan["captionText"].splitlines()[0], 70), fontsize=15, color=STYLE["primary"], loc="left", pad=12)
        if col_count == 1:
            col_widths = [0.96]
        else:
            first_width = 0.22 if col_count >= 6 else 0.18
            other_width = (0.96 - first_width) / (col_count - 1)
            col_widths = [first_width] + [other_width] * (col_count - 1)
        table = ax.table(
            cellText=visible_rows,
            colLabels=header_labels,
            bbox=[0.02, 0.03, 0.96, 0.86 if plan.get("captionText") else 0.92],
            cellLoc="center",
            colLoc="center",
            colWidths=col_widths,
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.0 if col_count >= 7 else 8.5)
        table.scale(1, 1.55)
        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_edgecolor(STYLE["grid"])
            cell.set_linewidth(0.65)
            if row_idx == 0:
                cell.set_facecolor(STYLE["primary"])
                cell.get_text().set_color("#FFFFFF")
                cell.get_text().set_fontweight("bold")
            elif col_idx == 0:
                cell.set_facecolor(STYLE["firstColumnFill"])
                cell.get_text().set_color(STYLE["primaryDark"])
                cell.get_text().set_fontweight("bold")
            elif row_idx % 2 == 0:
                cell.set_facecolor(STYLE["lightFill"])
            else:
                cell.set_facecolor(STYLE["background"])
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs
