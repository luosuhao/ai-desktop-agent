from __future__ import annotations

import math
from pathlib import Path

from .common import (
    STYLE,
    get_render_rows,
    is_percent_like,
    parse_number,
    rows_with_chart_data,
    save_figure,
    setup_matplotlib,
    title_for_plan,
    valid_numeric_series,
)
from .table_image import render_table_image


def render_trend_chart(plan: dict, manifest_dir: Path, output_path: Path) -> list[dict]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    if not data_rows:
        return render_table_image(plan, manifest_dir, output_path)
    series = valid_numeric_series(plan, headers, data_rows, require_label=True)
    kept_rows = rows_with_chart_data(data_rows, series)
    if not series or not kept_rows:
        return render_table_image(plan, manifest_dir, output_path)
    x_labels = [row[0] for _row_idx, row in kept_rows]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    all_values: list[float] = []
    xs = list(range(len(kept_rows)))
    for series_idx, item in enumerate(series):
        values = []
        for row_idx, row in kept_rows:
            col_idx = item["colIndex"]
            number = parse_number(row[col_idx] if col_idx < len(row) else "")
            values.append(float("nan") if number is None else number)
            if number is not None:
                all_values.append(number)
        if not any(not math.isnan(value) for value in values):
            continue
        ax.plot(xs, values, linewidth=1.8, color=STYLE["series"][series_idx % len(STYLE["series"])], label=item["label"])
    ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
    tick_step = max(1, math.ceil(len(x_labels) / 10))
    tick_positions = xs[::tick_step]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([x_labels[idx] for idx in tick_positions], rotation=30, ha="right", fontsize=8)
    if is_percent_like(headers, all_values):
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(3, len(series)), frameon=False, fontsize=8)
    save_figure(fig, output_path)
    return [{"page": 1, "path": output_path}]
