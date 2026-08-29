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


def _max_abs_value(series: dict) -> float:
    values = [abs(value) for value in series.get("values", []) if value is not None and not math.isnan(value)]
    return max(values) if values else 0.0


def _is_amount_like(label: str) -> bool:
    return any(token in label for token in ["万元", "金额", "市值", "规模", "价值"])


def _is_ratio_like(series: dict) -> bool:
    label = series.get("label", "")
    if _is_amount_like(label):
        return False
    ratio_tokens = ["%", "率", "占比", "比例", "贡献", "仓位", "增长"]
    return any(token in label for token in ratio_tokens) or _max_abs_value(series) <= 2.0


def _composition_priority(series: dict) -> tuple[int, int]:
    label = series.get("label", "")
    priority_tokens = ["贡献", "收益率", "增长", "占比", "比例", "仓位"]
    for idx, token in enumerate(priority_tokens):
        if token in label:
            return (idx, -int(series.get("validCount", 0)))
    return (len(priority_tokens), -int(series.get("validCount", 0)))


def _select_composition_series(series: list[dict]) -> list[dict]:
    ratio_series = [item for item in series if _is_ratio_like(item)]
    if ratio_series:
        return sorted(ratio_series, key=_composition_priority)[:4]

    buckets: dict[int, list[dict]] = {}
    for item in series:
        max_value = _max_abs_value(item)
        if max_value <= 0:
            continue
        bucket = int(math.floor(math.log10(max_value)))
        buckets.setdefault(bucket, []).append(item)
    if not buckets:
        return []
    best_bucket = max(buckets.items(), key=lambda pair: len(pair[1]))[0]
    return buckets[best_bucket][:3]


def render_composition_chart(plan: dict, manifest_dir: Path, output_base: Path) -> list[dict]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    series = _select_composition_series(valid_numeric_series(plan, headers, data_rows, require_label=True))
    kept_rows = rows_with_chart_data(data_rows, series)
    if not kept_rows or not series:
        return render_table_image(plan, manifest_dir, output_base)
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 14)
    outputs: list[dict] = []
    pages = paged_rows(kept_rows, per_page)
    for page_idx, page_rows in enumerate(pages, start=1):
        path = output_base if len(pages) == 1 else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        categories = [wrap_label(row[0], 10) for _row_idx, row in page_rows]
        y = list(range(len(page_rows)))
        height = min(0.8 / max(len(series), 1), 0.24)
        fig_height = max(5.6, min(12, len(page_rows) * 0.42 + 2.2))
        fig, ax = plt.subplots(figsize=(11.5, fig_height))
        all_values: list[float] = []
        for series_idx, item in enumerate(series):
            values: list[float] = []
            for row_idx, row in page_rows:
                col_idx = item["colIndex"]
                number = parse_number(row[col_idx] if col_idx < len(row) else "")
                values.append(float("nan") if number is None else number)
                if number is not None:
                    all_values.append(number)
            if not any(not math.isnan(value) for value in values):
                continue
            offset = (series_idx - (len(series) - 1) / 2) * height
            ax.barh([pos + offset for pos in y], values, height=height, label=item["label"], color=STYLE["series"][series_idx % len(STYLE["series"])])
        ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
        ax.set_yticks(y)
        ax.set_yticklabels(categories, fontsize=8)
        ax.invert_yaxis()
        if is_percent_like(headers, all_values):
            ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(axis="x", color=STYLE["grid"], linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=min(4, len(series)), frameon=False, fontsize=8)
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs
