#!/usr/bin/env python3
"""Step 3A-new: build a compact editable PPT generation plan from sheet Markdown assets."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECTION_RULES = [
    ("01", "组合业绩分析", ["组合业绩情况", "组合业绩归因", "组合资产配置", "今年以来资产配置回顾"]),
    ("02", "投资操作回顾", ["组合固收投资回顾", "组合权益投资回顾"]),
    ("03", "下阶段市场研判及组合操作策略", ["市场回顾", "投资策略"]),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact editable PPT plan from sheet-md-assets.")
    parser.add_argument("project_dir", type=Path, help="Project directory containing sheet-md-assets.")
    parser.add_argument("--template-id", default="fund-pension-annuity", help="Template folder under ppt-template-generator/templates.")
    parser.add_argument("--template-root", type=Path, help="Template root. Defaults to <skill>/templates.")
    parser.add_argument("--max-visuals-per-slide", type=int, default=3)
    parser.add_argument("--max-bullets-per-slide", type=int, default=5)
    parser.add_argument("--max-blocks-per-slide", type=int, default=2)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def default_template_root() -> Path:
    return Path(__file__).resolve().parents[1] / "templates"


def pick_template(registry: dict[str, Any], role: str) -> dict[str, Any]:
    entries = (registry.get("roles") or {}).get(role) or []
    if not entries:
        return {"role": role, "sourceSlide": None, "pptLayoutName": None}
    entry = entries[0]
    return {
        "role": role,
        "sourceSlide": entry.get("sourceSlide"),
        "pptLayoutName": entry.get("pptLayoutName"),
        "layoutTarget": entry.get("layoutTarget"),
    }


def clean_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^[\u2022\u25cf\u25a0\-\s]+", "", text).strip()
    return text


def is_noise_bullet(text: str) -> bool:
    text = clean_text(text)
    if not text:
        return True
    if len(text) <= 12 and re.search(r"(回顾|分析|观点|情况|投资回顾)[:：]?$", text):
        return True
    if re.match(r"^(注|备注|数据区间|时间区间|资料来源|来源|ytm|YTM|静态收益率)[:：]", text):
        return True
    if "图表显示" in text:
        return True
    if re.fullmatch(r"[\u4e00-\u9fa5A-Za-z0-9（）()%/ ]{2,24}", text) and "。" not in text and "，" not in text:
        if any(word in text for word in ["分布", "排名", "类型", "类别"]):
            return True
    digit_count = len(re.findall(r"\d", text))
    token_count = len([item for item in re.split(r"\s+", text) if item])
    punctuation_count = len(re.findall(r"[，。；：、]", text))
    if token_count >= 8 and digit_count >= 8 and punctuation_count == 0:
        return True
    return False


def clean_display_metadata(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s+-\s+-\s+-\s+\d{6}\s+\d{4}-\d{2}-\d{2}$", "", text)
    text = re.sub(r"\s+\d{6}\s+\d{4}-\d{2}-\d{2}$", "", text)
    text = re.sub(r"\s+-\s+-\s+-$", "", text).strip()
    match = re.match(r"^\d+\s+(固收|权益)\s+\S{1,6}\s+\d+\s+([^\s]+)\s+(.+)$", text)
    if match:
        asset_class, topic, rest = match.groups()
        topic = "" if topic == "总观点" else topic
        prefix = f"{asset_class}{topic}观点" if topic else f"{asset_class}总观点"
        text = f"{prefix}：{rest}"
    text = text.replace("建议在在", "建议在")
    text = text.replace("部分部分", "部分")
    text = re.sub(r"\s+-\s+(?=展望)", " ", text)
    return clean_text(text)


def compress_text(text: str, max_len: int = 118) -> str:
    text = clean_display_metadata(text)
    if len(text) <= max_len:
        return text
    pieces = [piece.strip() for piece in re.split(r"(?<=[。；;])", text) if piece.strip()]
    summary = ""
    for piece in pieces:
        if len(summary) + len(piece) <= max_len:
            summary += piece
    if len(summary) >= 28:
        return summary.rstrip("，,；;。") + "。"
    cut = text[:max_len]
    for sep in ["。", "；", "，", "、", " "]:
        pos = cut.rfind(sep)
        if pos >= 42:
            cut = cut[:pos]
            break
    return cut.rstrip("，,；;、 ")


def markdown_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        if line.startswith("# "):
            return clean_text(line[2:])
    return fallback


def parse_sheet_md(path: Path, project_dir: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    title = markdown_title(lines, path.stem)
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    mode = ""

    def flush() -> None:
        nonlocal current
        if current and (current["viewpoints"] or current["visualAssets"]):
            low_density_block = len(current["viewpoints"]) <= 3 and len(current["visualAssets"]) <= 2
            for viewpoint in current["viewpoints"]:
                if low_density_block:
                    viewpoint["displayText"] = clean_display_metadata(viewpoint["sourceText"])
                    viewpoint["textTreatment"] = "clean_only"
                else:
                    viewpoint["displayText"] = compress_text(viewpoint["sourceText"])
                    viewpoint["textTreatment"] = "clean_and_compact"
            blocks.append(current)
        current = None

    for raw_line in lines:
        line = raw_line.strip()
        if line == "## 观点文字资产":
            flush()
            current = {"blockId": f"{path.stem}_block_{len(blocks) + 1:02d}", "viewpoints": [], "visualAssets": []}
            mode = "text"
            continue
        if line == "## 图片资产":
            if current is None or (mode == "image" and current["visualAssets"]):
                flush()
                current = {"blockId": f"{path.stem}_block_{len(blocks) + 1:02d}", "viewpoints": [], "visualAssets": []}
            mode = "image"
            continue
        if not line.startswith("- "):
            continue
        item = clean_text(line[2:])
        if mode == "text":
            if is_noise_bullet(item):
                continue
            current = current or {"blockId": f"{path.stem}_block_{len(blocks) + 1:02d}", "viewpoints": [], "visualAssets": []}
            current["viewpoints"].append({"sourceText": item, "displayText": clean_display_metadata(item)})
        elif mode == "image":
            current = current or {"blockId": f"{path.stem}_block_{len(blocks) + 1:02d}", "viewpoints": [], "visualAssets": []}
            abs_path = project_dir / item
            current["visualAssets"].append(
                {
                    "relativePath": item,
                    "absolutePath": str(abs_path),
                    "assetRoot": item.split("/", 1)[0] if "/" in item else "",
                    "exists": abs_path.exists(),
                }
            )

    flush()
    return {"sheetId": path.stem, "title": title, "markdown": str(path.relative_to(project_dir)).replace("\\", "/"), "blocks": blocks}


def load_sheet_assets(project_dir: Path) -> list[dict[str, Any]]:
    md_dir = project_dir / "sheet-md-assets"
    index_path = md_dir / "sheet-md-manifest.json"
    sheets: list[dict[str, Any]] = []
    if index_path.exists():
        index = read_json(index_path)
        for item in index.get("sheets", []):
            md_path = project_dir / item.get("markdown", "")
            if md_path.exists():
                sheet = parse_sheet_md(md_path, project_dir)
                sheet["order"] = item.get("order", len(sheets) + 1)
                sheet["groupId"] = item.get("groupId") or sheet["sheetId"]
                sheet["sheet"] = item.get("sheet") or sheet["title"]
                sheets.append(sheet)
    else:
        for order, md_path in enumerate(sorted(md_dir.glob("*.md")), start=1):
            sheet = parse_sheet_md(md_path, project_dir)
            sheet["order"] = order
            sheet["groupId"] = sheet["sheetId"]
            sheet["sheet"] = sheet["title"]
            sheets.append(sheet)
    return sorted(sheets, key=lambda item: item.get("order", 9999))


def section_plan(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {sheet.get("groupId"): sheet for sheet in sheets}
    used: set[str] = set()
    sections: list[dict[str, Any]] = []
    for section_id, title, ids in SECTION_RULES:
        existing = [group_id for group_id in ids if group_id in by_id]
        if existing:
            sections.append({"sectionId": section_id, "title": title, "groupIds": existing})
            used.update(existing)
    data_ids = [sheet["groupId"] for sheet in sheets if sheet["groupId"] not in used and str(sheet["groupId"]).endswith("_数据")]
    if data_ids:
        sections.append({"sectionId": f"{len(sections) + 1:02d}", "title": "补充数据图表", "groupIds": data_ids})
        used.update(data_ids)
    remaining = [sheet["groupId"] for sheet in sheets if sheet["groupId"] not in used]
    if remaining:
        sections.append({"sectionId": f"{len(sections) + 1:02d}", "title": "其他内容", "groupIds": remaining})
    return sections


def empty_page(sheet: dict[str, Any], page_index: int) -> dict[str, Any]:
    suffix = "" if page_index == 1 else f"（{page_index}）"
    return {
        "title": f"{sheet['title']}{suffix}",
        "sheetId": sheet["sheetId"],
        "groupId": sheet.get("groupId"),
        "markdown": sheet.get("markdown"),
        "contentBlocks": [],
        "bullets": [],
        "visualAssets": [],
        "deferredVisualAssets": [],
        "deferredBullets": [],
    }


def visual_count(page: dict[str, Any]) -> int:
    return len(page["visualAssets"])


def bullet_count(page: dict[str, Any]) -> int:
    return len(page["bullets"])


def can_pack(page: dict[str, Any], block: dict[str, Any], max_visuals: int, max_bullets: int, max_blocks: int) -> bool:
    if len(page["contentBlocks"]) >= max_blocks:
        return False
    if visual_count(page) + len(block["visualAssets"]) > max_visuals:
        return False
    if bullet_count(page) + len(block["viewpoints"]) > max_bullets:
        return False
    return True


def add_block_to_page(page: dict[str, Any], block: dict[str, Any], visuals: list[dict[str, Any]] | None = None, bullets: list[dict[str, Any]] | None = None) -> None:
    page["contentBlocks"].append(block["blockId"])
    page["bullets"].extend(bullets if bullets is not None else block["viewpoints"])
    page["visualAssets"].extend(visuals if visuals is not None else block["visualAssets"])


def visual_relevance_score(visual: dict[str, Any], index: int) -> tuple[int, int, int]:
    """Prefer source pictures, then rendered visuals, while keeping MD order as a tiebreaker."""
    path = visual.get("relativePath", "")
    source_picture_score = 2 if path.startswith("picture-assets/") else 1
    chart_score = 1 if any(token in path for token in ["chart", "image", "table"]) else 0
    return (source_picture_score, chart_score, -index)


def strongest_visuals(visuals: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexed = list(enumerate(visuals))
    ranked = sorted(indexed, key=lambda item: visual_relevance_score(item[1], item[0]), reverse=True)
    selected_indexes = {index for index, _ in ranked[:limit]}
    selected = [visual for index, visual in indexed if index in selected_indexes]
    deferred = [visual for index, visual in indexed if index not in selected_indexes]
    for visual in selected:
        visual["selectionReason"] = "strongest_related_visual_for_text_block"
    for visual in deferred:
        visual["selectionReason"] = "deferred_overflow_from_text_visual_block"
    return selected, deferred


def layout_for_page(page: dict[str, Any]) -> str:
    visuals = len(page["visualAssets"])
    bullets = len(page["bullets"])
    if visuals >= 3 and bullets:
        return "summary_plus_three_visuals"
    if visuals == 2 and bullets:
        return "summary_plus_two_visuals"
    if visuals == 1 and bullets:
        return "summary_plus_one_visual"
    if visuals >= 3:
        return "three_visuals_grid"
    if visuals == 2:
        return "two_visuals_grid"
    if visuals == 1:
        return "one_visual"
    return "text_only_compact"


def sheet_pages(sheet: dict[str, Any], max_visuals: int, max_bullets: int, max_blocks: int) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    def flush_pending() -> None:
        nonlocal pending
        if pending and (pending["bullets"] or pending["visualAssets"]):
            pages.append(pending)
        pending = None

    for block in sheet["blocks"]:
        visuals = block["visualAssets"]
        bullets = block["viewpoints"]
        if bullets and len(visuals) > max_visuals:
            flush_pending()
            selected_visuals, deferred_visuals = strongest_visuals(visuals, max_visuals)
            page = empty_page(sheet, len(pages) + 1)
            add_block_to_page(page, block, visuals=selected_visuals, bullets=bullets[:max_bullets])
            page["deferredVisualAssets"].extend(deferred_visuals)
            overflow_bullets = bullets[max_bullets:]
            if 0 < len(overflow_bullets) <= 2:
                page["deferredBullets"].extend(overflow_bullets)
                overflow_bullets = []
            pages.append(page)
            for start in range(0, len(overflow_bullets), max_bullets):
                page = empty_page(sheet, len(pages) + 1)
                add_block_to_page(page, block, visuals=[], bullets=overflow_bullets[start : start + max_bullets])
                pages.append(page)
            continue

        if not visuals and len(bullets) > max_bullets:
            flush_pending()
            for start in range(0, len(bullets), max_bullets):
                page = empty_page(sheet, len(pages) + 1)
                add_block_to_page(page, block, visuals=[], bullets=bullets[start : start + max_bullets])
                pages.append(page)
            continue

        if len(visuals) > max_visuals:
            flush_pending()
            chunks = [visuals[i : i + max_visuals] for i in range(0, len(visuals), max_visuals)]
            for chunk_index, chunk in enumerate(chunks, start=1):
                page = empty_page(sheet, len(pages) + 1)
                chunk_bullets = bullets[:max_bullets] if chunk_index == 1 else []
                add_block_to_page(page, block, visuals=chunk, bullets=chunk_bullets)
                is_last_underfilled_visual_only = chunk_index == len(chunks) and len(chunk) < max_visuals and not chunk_bullets
                if is_last_underfilled_visual_only:
                    pending = page
                else:
                    pages.append(page)
            overflow_bullets = bullets[max_bullets:]
            for start in range(0, len(overflow_bullets), max_bullets):
                page = empty_page(sheet, len(pages) + 1)
                add_block_to_page(page, block, visuals=[], bullets=overflow_bullets[start : start + max_bullets])
                pages.append(page)
            continue

        if visuals and len(bullets) > max_bullets:
            flush_pending()
            page = empty_page(sheet, len(pages) + 1)
            add_block_to_page(page, block, visuals=visuals, bullets=bullets[:max_bullets])
            overflow_bullets = bullets[max_bullets:]
            if 0 < len(overflow_bullets) <= 2:
                page["deferredBullets"].extend(overflow_bullets)
                overflow_bullets = []
            pages.append(page)
            for start in range(0, len(overflow_bullets), max_bullets):
                page = empty_page(sheet, len(pages) + 1)
                add_block_to_page(page, block, visuals=[], bullets=overflow_bullets[start : start + max_bullets])
                pages.append(page)
            continue

        if pending is None:
            pending = empty_page(sheet, len(pages) + 1)
        if can_pack(pending, block, max_visuals, max_bullets, max_blocks):
            add_block_to_page(pending, block)
        else:
            flush_pending()
            pending = empty_page(sheet, len(pages) + 1)
            add_block_to_page(pending, block)

    flush_pending()
    for page in pages:
        page["layout"] = layout_for_page(page)
        page["density"] = {
            "compact": True,
            "visualCount": len(page["visualAssets"]),
            "deferredVisualCount": len(page["deferredVisualAssets"]),
            "bulletCount": len(page["bullets"]),
            "deferredBulletCount": len(page["deferredBullets"]),
            "contentBlockCount": len(page["contentBlocks"]),
        }
    return pages


def deck_title(project_dir: Path) -> tuple[str, str]:
    manifest_path = project_dir / "excel-content-manifest.json"
    title = "中国银行股份有限公司企业年金计划 国泰基金组合投资汇报"
    date = "2026年7月"
    if not manifest_path.exists():
        return title, date
    try:
        manifest = read_json(manifest_path)
    except Exception:
        return title, date
    meta = manifest.get("deckMeta") or {}
    title = meta.get("title") or title
    date = meta.get("date") or date
    return title, date


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = args.project_dir.resolve()
    template_root = args.template_root or default_template_root()
    registry_path = template_root / args.template_id / "layout-registry.json"
    registry = read_json(registry_path)
    title, report_date = deck_title(project_dir)
    sheets = load_sheet_assets(project_dir)
    sections = section_plan(sheets)
    by_id = {sheet["groupId"]: sheet for sheet in sheets}

    slides: list[dict[str, Any]] = []
    slide_no = 1

    def add_slide(role: str, slide_title: str, content: dict[str, Any], layout_hint: dict[str, Any] | None = None) -> None:
        nonlocal slide_no
        slides.append(
            {
                "slideNumber": slide_no,
                "slideId": f"s{slide_no:03d}",
                "role": role,
                "title": slide_title,
                "template": pick_template(registry, role),
                "content": content,
                "layoutHint": layout_hint or {},
            }
        )
        slide_no += 1

    add_slide("cover", title, {"title": title, "date": report_date}, {"editPolicy": "text_only_preserve_style"})
    add_slide(
        "toc",
        "目录",
        {"items": [{"index": section["sectionId"], "title": section["title"]} for section in sections if section["title"] != "补充数据图表"]},
        {"editPolicy": "text_only_preserve_style"},
    )

    for section in sections:
        add_slide(
            "section",
            section["title"],
            {"sectionIndex": section["sectionId"], "sectionTitle": section["title"]},
            {"editPolicy": "text_only_preserve_style"},
        )
        for group_id in section["groupIds"]:
            sheet = by_id.get(group_id)
            if not sheet:
                continue
            for page in sheet_pages(sheet, args.max_visuals_per_slide, args.max_bullets_per_slide, args.max_blocks_per_slide):
                add_slide(
                    "content",
                    page["title"],
                    {
                        "sheet": sheet.get("sheet"),
                        "groupId": group_id,
                        "markdown": sheet.get("markdown"),
                        "contentBlocks": page["contentBlocks"],
                        "bullets": page["bullets"],
                        "visualAssets": page["visualAssets"],
                        "deferredVisualAssets": page["deferredVisualAssets"],
                        "deferredBullets": page["deferredBullets"],
                    },
                    {
                        "editPolicy": "semi_free_inside_content_zone",
                        "arrangement": page["layout"],
                        "density": page["density"],
                        "preserveTemplateChrome": True,
                        "maxVisualsPerSlide": args.max_visuals_per_slide,
                        "maxBulletsPerSlide": args.max_bullets_per_slide,
                    },
                )

    add_slide("closing", "封底", {"leaveUnchanged": True}, {"editPolicy": "leave_unchanged"})

    content_slides = [slide for slide in slides if slide["role"] == "content"]
    visuals = [visual for slide in content_slides for visual in slide["content"].get("visualAssets", [])]
    deferred_visuals = [visual for slide in content_slides for visual in slide["content"].get("deferredVisualAssets", [])]
    bullets = [bullet for slide in content_slides for bullet in slide["content"].get("bullets", [])]
    deferred_bullets = [bullet for slide in content_slides for bullet in slide["content"].get("deferredBullets", [])]
    return {
        "version": 1,
        "stage": "Step 3A-new",
        "generatedAt": now_iso(),
        "projectDir": str(project_dir),
        "template": {
            "templateId": args.template_id,
            "registry": str(registry_path),
            "sourcePptx": str(template_root / args.template_id / "source.pptx"),
        },
        "rules": {
            "coverTocSection": "replace text only; preserve all template styling, logos, backgrounds, and lines",
            "closing": "leave unchanged",
            "content": "semi-free inside content-safe zone; preserve title/logo/footer/chrome",
            "density": "compact: pack up to 3 visuals and up to 5 concise viewpoint bullets per content slide",
            "text": "displayText is slide-ready; sourceText keeps the full editable source",
        },
        "summary": {
            "slideCount": len(slides),
            "contentSlideCount": len(content_slides),
            "sectionCount": len(sections),
            "sheetCount": len(sheets),
            "visualAssetCount": len(visuals),
            "deferredVisualAssetCount": len(deferred_visuals),
            "pictureAssetCount": sum(1 for visual in visuals if visual.get("assetRoot") == "picture-assets"),
            "pythonTableAssetCount": sum(1 for visual in visuals if visual.get("assetRoot") == "python_table"),
            "viewpointBulletCount": len(bullets),
            "deferredBulletCount": len(deferred_bullets),
            "missingVisualAssetCount": sum(1 for visual in visuals if not visual.get("exists")),
            "maxVisualsPerContentSlide": max((len(slide["content"].get("visualAssets", [])) for slide in content_slides), default=0),
        },
        "sections": sections,
        "slides": slides,
    }


def write_plan_md(plan: dict[str, Any], path: Path) -> None:
    lines: list[str] = [
        "# PPT Generation Plan",
        "",
        f"- 模板: {plan['template']['templateId']}",
        f"- 总页数: {plan['summary']['slideCount']}",
        f"- 内容页: {plan['summary']['contentSlideCount']}",
        f"- 视觉资产: {plan['summary']['visualAssetCount']}",
        f"- 缺失视觉资产: {plan['summary']['missingVisualAssetCount']}",
        "",
    ]
    for slide in plan["slides"]:
        lines.append(f"## {slide['slideNumber']:02d}. {slide['title']} [{slide['role']}]")
        if slide["role"] == "content":
            hint = slide.get("layoutHint", {})
            lines.append(f"- 布局: {hint.get('arrangement')}")
            bullets = slide["content"].get("bullets", [])
            visuals = slide["content"].get("visualAssets", [])
            deferred_visuals = slide["content"].get("deferredVisualAssets", [])
            deferred_bullets = slide["content"].get("deferredBullets", [])
            if bullets:
                lines.append("- 观点:")
                for bullet in bullets:
                    lines.append(f"  - {bullet['displayText']}")
            if visuals:
                lines.append("- 图片:")
                for visual in visuals:
                    missing = "" if visual.get("exists") else " (missing)"
                    lines.append(f"  - {visual['relativePath']}{missing}")
            if deferred_visuals:
                lines.append("- 压缩未入页图片:")
                for visual in deferred_visuals:
                    lines.append(f"  - {visual['relativePath']}")
            if deferred_bullets:
                lines.append("- 压缩未入页观点:")
                for bullet in deferred_bullets:
                    lines.append(f"  - {bullet['displayText']}")
        elif slide["role"] == "toc":
            for item in slide["content"].get("items", []):
                lines.append(f"- {item['index']} {item['title']}")
        elif slide["role"] == "section":
            lines.append(f"- 章节: {slide['content'].get('sectionIndex')} {slide['content'].get('sectionTitle')}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_dir = args.project_dir.resolve()
    output_json = args.output_json or (project_dir / "ppt-generation-plan.json")
    output_md = args.output_md or (project_dir / "ppt-generation-plan.md")
    plan = build_plan(args)
    output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_plan_md(plan, output_md)
    if args.pretty:
        print(json.dumps(plan["summary"], ensure_ascii=False, indent=2))
        print(f"planJson: {output_json}")
        print(f"planMd: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
