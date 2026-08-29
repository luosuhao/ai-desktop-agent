from __future__ import annotations

import math
from pathlib import Path

from .common import (
    STYLE,
    get_render_rows,
    is_percent_like,
    paged_rows,
    parse_number,
    rows_with_chart_data,
    save_figure,
    setup_matplotlib,
    title_for_plan,
    valid_numeric_series,
    wrap_label,
)
from .table_image import render_table_image


def render_category_chart(plan: dict, manifest_dir: Path, output_base: Path) -> list[dict]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    series = valid_numeric_series(plan, headers, data_rows, require_label=True)
    kept_rows = rows_with_chart_data(data_rows, series)
    if not kept_rows or not series:
        return render_table_image(plan, manifest_dir, output_base)
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 20)
    pages = paged_rows(kept_rows, per_page)
    outputs: list[dict] = []
    for page_idx, page_rows in enumerate(pages, start=1):
        path = output_base if len(pages) == 1 else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        categories = [wrap_label(row[0], 8) for _row_idx, row in page_rows]
        x = list(range(len(page_rows)))
        width = min(0.8 / max(len(series), 1), 0.22)
        fig_width = max(10, min(18, len(page_rows) * 0.55 + 4))
        fig, ax = plt.subplots(figsize=(fig_width, 6.2))
        all_values: list[float] = []
        for series_idx, item in enumerate(series):
            values = []
            for row_idx, row in page_rows:
                col_idx = item["colIndex"]
                number = parse_number(row[col_idx] if col_idx < len(row) else "")
                values.append(float("nan") if number is None else number)
                if number is not None:
                    all_values.append(number)
            if not any(not math.isnan(value) for value in values):
                continue
            offset = (series_idx - (len(series) - 1) / 2) * width
            ax.bar([pos + offset for pos in x], values, width=width, label=item["label"], color=STYLE["series"][series_idx % len(STYLE["series"])])
        ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=8)
        if is_percent_like(headers, all_values):
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(4, len(series)), frameon=False, fontsize=8)
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs
