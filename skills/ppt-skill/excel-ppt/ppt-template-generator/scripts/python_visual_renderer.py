#!/usr/bin/env python3
"""Render Step 2B Python visual assets from visual-asset-plan.json."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
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
    "series": ["#9E0116", "#6F0010", "#7F7F7F", "#B0B0B0", "#BF9D5A", "#C9CDD4", "#333333"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Step 2B PNG visual assets into python_table/.")
    parser.add_argument("plan", type=Path, help="Path to visual-asset-plan.json")
    parser.add_argument("--manifest", type=Path, help="Defaults to plan.sourceManifest")
    parser.add_argument("--output-dir", type=Path, help="Defaults to python_table beside the manifest")
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str, fallback: str = "asset") -> str:
    slug = re.sub(r"[^\w.-]+", "_", str(value).strip(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug or fallback


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
    text = text.replace(",", "").replace("，", "")
    percent = text.endswith("%")
    if percent:
        text = text[:-1]
    text = re.sub(r"^[^\d.+-]+", "", text)
    text = re.sub(r"[^\d.+-]+$", "", text)
    if not text or text in {"+", "-", "."}:
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
    return text if len(text) <= limit else text[: limit - 1] + "…"


def wrap_label(value: Any, width: int = 8) -> str:
    text = str(value or "").strip()
    if len(text) <= width:
        return text
    return "\n".join(text[idx : idx + width] for idx in range(0, len(text), width))


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


def is_percent_like(headers: list[str], values: list[float]) -> bool:
    header_text = " ".join(headers)
    if "%" in header_text or any(token in header_text for token in ["收益率", "占比", "比例", "仓位", "贡献"]):
        return True
    finite = [abs(value) for value in values if value is not None and not math.isnan(value)]
    return bool(finite) and max(finite) <= 2.0


def save_figure(fig: Any, output_path: Path) -> None:
    fig.savefig(output_path, dpi=220, bbox_inches="tight", facecolor=STYLE["background"])
    import matplotlib.pyplot as plt

    plt.close(fig)


def render_trend_chart(plan: dict[str, Any], manifest_dir: Path, output_path: Path) -> list[dict[str, Any]]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    if not data_rows:
        return render_table_image(plan, manifest_dir, output_path)
    x_labels = [row[0] if row else "" for row in data_rows]
    numeric_indices = numeric_column_indices(plan)
    if not numeric_indices:
        return render_table_image(plan, manifest_dir, output_path)
    fig, ax = plt.subplots(figsize=(11, 5.8))
    all_values: list[float] = []
    xs = list(range(len(data_rows)))
    for series_idx, col_idx in enumerate(numeric_indices):
        values = []
        for row in data_rows:
            number = parse_number(row[col_idx] if col_idx < len(row) else "")
            values.append(float("nan") if number is None else number)
            if number is not None:
                all_values.append(number)
        label = headers[col_idx] if col_idx < len(headers) else f"series {series_idx + 1}"
        ax.plot(xs, values, linewidth=1.8, color=STYLE["series"][series_idx % len(STYLE["series"])], label=label)
    ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
    tick_step = max(1, math.ceil(len(x_labels) / 10))
    tick_positions = xs[::tick_step]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([x_labels[idx] for idx in tick_positions], rotation=30, ha="right", fontsize=8)
    if is_percent_like(headers, all_values):
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=min(3, len(numeric_indices)), frameon=False, fontsize=8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_figure(fig, output_path)
    return [{"page": 1, "path": output_path}]


def paged_rows(rows: list[list[str]], per_page: int) -> list[list[list[str]]]:
    if not rows:
        return [[]]
    return [rows[idx : idx + per_page] for idx in range(0, len(rows), per_page)]


def render_category_chart(plan: dict[str, Any], manifest_dir: Path, output_base: Path) -> list[dict[str, Any]]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    numeric_indices = numeric_column_indices(plan)
    if not data_rows or not numeric_indices:
        return render_table_image(plan, manifest_dir, output_base)
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 20)
    pages = paged_rows(data_rows, per_page)
    outputs: list[dict[str, Any]] = []
    for page_idx, page_rows in enumerate(pages, start=1):
        path = output_base if len(pages) == 1 else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        categories = [wrap_label(row[0], 8) for row in page_rows]
        x = list(range(len(page_rows)))
        width = min(0.8 / max(len(numeric_indices), 1), 0.22)
        fig_width = max(10, min(18, len(page_rows) * 0.55 + 4))
        fig, ax = plt.subplots(figsize=(fig_width, 6.2))
        all_values: list[float] = []
        for series_idx, col_idx in enumerate(numeric_indices):
            values = []
            for row in page_rows:
                number = parse_number(row[col_idx] if col_idx < len(row) else "")
                values.append(0 if number is None else number)
                if number is not None:
                    all_values.append(number)
            offset = (series_idx - (len(numeric_indices) - 1) / 2) * width
            label = headers[col_idx] if col_idx < len(headers) else f"series {series_idx + 1}"
            ax.bar([pos + offset for pos in x], values, width=width, label=label, color=STYLE["series"][series_idx % len(STYLE["series"])])
        ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=8)
        if is_percent_like(headers, all_values):
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(4, len(numeric_indices)), frameon=False, fontsize=8)
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs


def render_composition_chart(plan: dict[str, Any], manifest_dir: Path, output_base: Path) -> list[dict[str, Any]]:
    setup_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    numeric_indices = numeric_column_indices(plan)
    if not data_rows or not numeric_indices:
        return render_table_image(plan, manifest_dir, output_base)
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 20)
    outputs: list[dict[str, Any]] = []
    for page_idx, page_rows in enumerate(paged_rows(data_rows, per_page), start=1):
        path = output_base if len(data_rows) <= per_page else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        categories = [wrap_label(row[0], 8) for row in page_rows]
        xs = list(range(len(page_rows)))
        bottoms = [0.0 for _ in page_rows]
        fig_width = max(10, min(18, len(page_rows) * 0.55 + 4))
        fig, ax = plt.subplots(figsize=(fig_width, 6.2))
        all_values: list[float] = []
        for series_idx, col_idx in enumerate(numeric_indices):
            values: list[float] = []
            for row in page_rows:
                number = parse_number(row[col_idx] if col_idx < len(row) else "")
                values.append(0 if number is None else number)
                if number is not None:
                    all_values.append(number)
            label = headers[col_idx] if col_idx < len(headers) else f"series {series_idx + 1}"
            ax.bar(xs, values, bottom=bottoms, width=0.58, label=label, color=STYLE["series"][series_idx % len(STYLE["series"])])
            bottoms = [bottom + value for bottom, value in zip(bottoms, values)]
        ax.set_title(title_for_plan(plan), fontsize=15, color=STYLE["text"], pad=14)
        ax.set_xticks(xs)
        ax.set_xticklabels(categories, fontsize=8)
        if is_percent_like(headers, all_values):
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        ax.grid(axis="y", color=STYLE["grid"], linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=min(4, len(numeric_indices)), frameon=False, fontsize=8)
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs


def render_table_image(plan: dict[str, Any], manifest_dir: Path, output_base: Path) -> list[dict[str, Any]]:
    setup_matplotlib()
    import matplotlib.pyplot as plt

    headers, data_rows, _all_rows = get_render_rows(plan, manifest_dir)
    if not headers:
        headers = ["内容"]
    per_page = int(plan.get("recommendedVisual", {}).get("pagination", {}).get("rowsPerPage") or 24)
    pages = paged_rows(data_rows, per_page)
    outputs: list[dict[str, Any]] = []
    for page_idx, page_rows in enumerate(pages, start=1):
        path = output_base if len(pages) == 1 else output_base.with_name(f"{output_base.stem}_p{page_idx:02d}{output_base.suffix}")
        visible_rows = [[compact_text(cell, 32) for cell in row[: len(headers)]] for row in page_rows]
        fig_height = max(2.4, min(12, 1.0 + 0.36 * (len(visible_rows) + 1)))
        fig_width = max(8, min(18, 1.5 * len(headers)))
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis("off")
        if plan.get("captionText"):
            ax.set_title(compact_text(plan["captionText"].splitlines()[0], 70), fontsize=14, color=STYLE["primary"], loc="left", pad=10)
        table = ax.table(
            cellText=visible_rows,
            colLabels=[compact_text(header, 18) for header in headers],
            loc="center",
            cellLoc="center",
            colLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.35)
        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_edgecolor(STYLE["grid"])
            cell.set_linewidth(0.6)
            if row_idx == 0:
                cell.set_facecolor(STYLE["primary"])
                cell.get_text().set_color("#FFFFFF")
                cell.get_text().set_fontweight("bold")
            elif col_idx == 0:
                cell.set_facecolor("#F3E6E8")
                cell.get_text().set_color(STYLE["primaryDark"])
            elif row_idx % 2 == 0:
                cell.set_facecolor(STYLE["lightFill"])
        save_figure(fig, path)
        outputs.append({"page": page_idx, "path": path})
    return outputs


def render_plan(plan: dict[str, Any], manifest_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    visual_type = plan.get("recommendedVisual", {}).get("visualType")
    if visual_type == "source_image":
        result: list[dict[str, Any]] = []
        for index, image in enumerate(plan.get("relatedImages", []), start=1):
            result.append(
                {
                    "page": index,
                    "path": str(manifest_dir / image.get("relativePath", "")),
                    "relativePath": image.get("relativePath", ""),
                    "renderType": "source_image",
                    "visualType": "source_image",
                    "route": plan.get("recommendedVisual", {}).get("route"),
                    "chartClass": None,
                    "imageId": image.get("imageId"),
                    "anchor": image.get("anchor"),
                    "captionText": image.get("nearbyText", ""),
                }
            )
        return result
    filename = f"{safe_name(plan.get('assetId', 'asset'))}_{visual_type}.png"
    output_base = output_dir / filename
    if visual_type == "trend_chart":
        rendered = render_trend_chart(plan, manifest_dir, output_base)
    elif visual_type == "category_chart":
        rendered = render_category_chart(plan, manifest_dir, output_base)
    elif visual_type == "composition_chart":
        rendered = render_composition_chart(plan, manifest_dir, output_base)
    else:
        rendered = render_table_image(plan, manifest_dir, output_base)
    result: list[dict[str, Any]] = []
    for item in rendered:
        path = item["path"]
        result.append(
            {
                "page": item["page"],
                "path": str(path),
                "relativePath": f"python_table/{path.name}",
                "renderType": "python_table_visual",
                "visualType": visual_type,
                "route": plan.get("recommendedVisual", {}).get("route"),
                "chartClass": plan.get("recommendedVisual", {}).get("chartClass"),
            }
        )
    return result


def update_manifest(manifest_path: Path, generated_by_block: dict[str, list[dict[str, Any]]]) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for group in manifest.get("contentGroups", []):
        for block in group.get("cellBlocks", []):
            block_id = block.get("blockId")
            if block_id in generated_by_block:
                block["selectedVisualAssets"] = generated_by_block[block_id]
                python_assets = [asset for asset in generated_by_block[block_id] if asset.get("renderType") == "python_table_visual"]
                if python_assets:
                    block["pythonVisualAssets"] = python_assets
        for table in group.get("tableAssets", []):
            block_id = table.get("blockId")
            if block_id in generated_by_block:
                table["selectedVisualAssets"] = generated_by_block[block_id]
                table["selectedVisualPath"] = generated_by_block[block_id][0]["relativePath"]
                python_assets = [asset for asset in generated_by_block[block_id] if asset.get("renderType") == "python_table_visual"]
                if python_assets:
                    table["pythonVisualAssets"] = python_assets
                    table["pythonVisualPath"] = python_assets[0]["relativePath"]
                else:
                    table.pop("pythonVisualAssets", None)
                    table.pop("pythonVisualPath", None)
        structured = group.get("structuredContent", {})
        for table in structured.get("tables", []):
            block_id = table.get("sourceBlockId")
            if block_id in generated_by_block:
                table["selectedVisualAssets"] = generated_by_block[block_id]
                table["selectedVisualPath"] = generated_by_block[block_id][0]["relativePath"]
                python_assets = [asset for asset in generated_by_block[block_id] if asset.get("renderType") == "python_table_visual"]
                if python_assets:
                    table["pythonVisualAssets"] = python_assets
                    table["pythonVisualPath"] = python_assets[0]["relativePath"]
                else:
                    table.pop("pythonVisualAssets", None)
                    table.pop("pythonVisualPath", None)
    manifest["pythonTableAssetsDir"] = "python_table"
    manifest["updatedAt"] = now_iso()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


from renderers.category_chart import render_category_chart  # noqa: E402
from renderers.composition_chart import render_composition_chart  # noqa: E402
from renderers.table_image import render_table_image  # noqa: E402
from renderers.trend_chart import render_trend_chart  # noqa: E402


def main() -> int:
    args = parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    manifest_path = args.manifest or Path(plan["sourceManifest"])
    manifest_dir = manifest_path.parent
    output_dir = args.output_dir or (manifest_dir / "python_table")
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_png in output_dir.glob("*.png"):
        old_png.unlink()

    generated_by_block: dict[str, list[dict[str, Any]]] = {}
    for table_plan in plan.get("tableVisualPlans", []):
        generated_by_block[table_plan["assetId"]] = render_plan(table_plan, manifest_dir, output_dir)

    assets = [
        {"sourceBlockId": block_id, "assets": assets}
        for block_id, assets in generated_by_block.items()
    ]
    assets_manifest = {
        "version": 1,
        "generatedAt": now_iso(),
        "sourcePlan": str(args.plan),
        "sourceManifest": str(manifest_path),
        "outputDir": str(output_dir),
        "assetCount": sum(len(item) for item in generated_by_block.values()),
        "tableAssetCount": len(generated_by_block),
        "assets": assets,
    }
    assets_path = manifest_dir / "python-table-assets.json"
    assets_path.write_text(json.dumps(assets_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_update_manifest:
        update_manifest(manifest_path, generated_by_block)

    if args.pretty:
        print(f"Wrote {assets_path}")
        print(f"Generated table visuals: {assets_manifest['assetCount']}")
        print(f"Updated manifest: {not args.no_update_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
