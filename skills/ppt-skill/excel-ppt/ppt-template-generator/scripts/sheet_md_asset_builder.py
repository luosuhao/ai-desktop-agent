#!/usr/bin/env python3
"""Build per-sheet Markdown assets with cleaned viewpoint text and image paths."""

from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path
from typing import Any


INVALID_FILENAME_CHARS = r'<>:"/\|?*'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-sheet Markdown assets for PPT generation.")
    parser.add_argument("manifest", type=Path, help="Path to excel-content-manifest.json")
    parser.add_argument("--output-dir", type=Path, help="Output folder. Defaults to sheet-md-assets beside manifest.")
    parser.add_argument("--pretty", action="store_true", help="Print summary.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_filename(name: str) -> str:
    cleaned = "".join("_" if ch in INVALID_FILENAME_CHARS else ch for ch in str(name or "sheet"))
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned or "sheet"


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_line(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"^[\u2022\u25cf\u25a0\-\s]+", "", text)
    return text.strip()


def parse_row(range_text: Any, default: int = 999999) -> int:
    text = str(range_text or "")
    match = re.search(r"([A-Z]+)(\d+)", text)
    if not match:
        return default
    return int(match.group(2))


def content_start_row(note: dict[str, Any], block_by_id: dict[str, dict[str, Any]] | None = None) -> int:
    row = parse_row(note.get("range"))
    block_by_id = block_by_id or {}
    block = block_by_id.get(note.get("sourceBlockId") or "") or {}
    sample_rows = note.get("sampleRows") or block.get("sampleRows") or []
    leading_empty_rows = 0
    for sample_row in sample_rows:
        values = [normalize_text(value) for value in sample_row]
        if any(values):
            break
        leading_empty_rows += 1
    return row + leading_empty_rows


def is_heading_only(text: str) -> bool:
    text = clean_line(text)
    return bool(re.match(r"^\d+[\.、]\s*[\u4e00-\u9fa5A-Za-z0-9（）()—\-]{2,35}$", text))


def numbered_heading(text: str) -> str:
    text = clean_line(text)
    match = re.match(r"^(\d+[\.、]\s*[^●■。；;]{2,60})", text)
    if not match:
        return ""
    heading = match.group(1).strip()
    if len(heading) > 35 and "—" not in heading and "-" not in heading:
        return ""
    return heading


def strip_numbered_heading(text: str) -> str:
    heading = numbered_heading(text)
    if not heading:
        return text
    return text[len(heading) :].strip()


def is_caption_or_note(text: str) -> bool:
    text = clean_line(text)
    if not text:
        return True
    if re.match(r"^(注|备注|数据区间|时间区间|资料来源|来源)[:：]", text):
        return True
    if text.startswith("图：") or text.startswith("图:"):
        return True
    return False


def looks_like_table_row(text: str) -> bool:
    text = clean_line(text)
    if not text:
        return True
    if "图表显示" in text:
        return True
    if text.endswith(" 是") or text.endswith(" 否"):
        return True
    if "_全" in text:
        return True
    tokens = [item for item in re.split(r"\s+", text) if item]
    decimal_count = len(re.findall(r"\d+\.\d{5,}", text))
    digit_count = len(re.findall(r"\d", text))
    punctuation_count = len(re.findall(r"[，。；：、]", text))
    if len(tokens) >= 4 and punctuation_count == 0:
        return True
    if decimal_count >= 2 and punctuation_count == 0:
        return True
    if len(tokens) >= 8 and digit_count >= 8 and punctuation_count == 0:
        return True
    if text.endswith(" 是") and decimal_count >= 1:
        return True
    return False


def split_viewpoints(text: Any) -> list[str]:
    raw = str(text or "").replace("\r", "\n")
    raw = re.sub(r"([●■])", r"\n\1", raw)
    parts: list[str] = []
    for part in re.split(r"[\n]+", raw):
        line = clean_line(part)
        line = strip_numbered_heading(line)
        line = clean_line(line)
        if not line:
            continue
        if is_caption_or_note(line) or is_heading_only(line) or looks_like_table_row(line):
            continue
        parts.append(line)
    return parts


def visual_entries(group: dict[str, Any], manifest_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    image_anchor_rows = {
        image.get("relativePath"): parse_row(image.get("anchor"))
        for image in group.get("imageAssets", [])
        if image.get("relativePath")
    }

    def add(relative_path: str, row: int, source_id: str, source_kind: str) -> None:
        if not relative_path or relative_path in seen:
            return
        if not (relative_path.startswith("python_table/") or relative_path.startswith("picture-assets/")):
            return
        if not (manifest_dir / relative_path).exists():
            return
        seen.add(relative_path)
        entries.append(
            {
                "kind": "visual",
                "row": row,
                "relativePath": relative_path,
                "sourceId": source_id,
                "sourceKind": source_kind,
            }
        )

    for table in group.get("tableAssets", []):
        row = parse_row(table.get("range"))
        for visual in table.get("selectedVisualAssets") or []:
            relative_path = visual.get("relativePath") or ""
            visual_row = image_anchor_rows.get(relative_path, row)
            add(relative_path, visual_row, table.get("blockId") or "", "table_selected_visual")

    for image in group.get("imageAssets", []):
        add(image.get("relativePath") or "", parse_row(image.get("anchor")), image.get("imageId") or "", "source_picture")

    return entries


def text_entries(group: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    block_by_id = {
        block.get("blockId"): block
        for block in group.get("cellBlocks", [])
        if block.get("blockId")
    }
    for note in group.get("textNotes", []):
        raw = str(note.get("text") or "")
        role = note.get("role") or ""
        if "图表显示" in raw:
            continue
        if role == "footnote" and "●" not in raw and "■" not in raw:
            continue
        points = split_viewpoints(note.get("text"))
        heading = numbered_heading(raw)
        if heading:
            entries.append(
                {
                    "kind": "boundary",
                    "row": content_start_row(note, block_by_id),
                    "sourceId": note.get("sourceBlockId") or "",
                    "sourceRange": note.get("range") or "",
                    "heading": heading,
                }
            )
        if not points:
            continue
        entries.append(
            {
                "kind": "text",
                "row": content_start_row(note, block_by_id),
                "sourceId": note.get("sourceBlockId") or "",
                "sourceRange": note.get("range") or "",
                "points": points,
            }
        )
    return entries


def build_sheet_sections(group: dict[str, Any], manifest_dir: Path) -> list[dict[str, Any]]:
    events = text_entries(group) + visual_entries(group, manifest_dir)
    has_boundaries = any(event["kind"] == "boundary" for event in events)
    order = {"boundary": 0, "text": 1, "visual": 2}
    events.sort(key=lambda item: (item["row"], order.get(item["kind"], 9), item.get("sourceId", "")))

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    seen_points: set[str] = set()

    def flush() -> None:
        nonlocal current
        if current and (current["viewpoints"] or current["images"]):
            sections.append(current)
        current = None

    for event in events:
        if event["kind"] == "boundary":
            flush()
            current = {
                "sourceId": event.get("sourceId"),
                "sourceRange": event.get("sourceRange"),
                "heading": event.get("heading", ""),
                "viewpoints": [],
                "images": [],
            }
        elif event["kind"] == "text":
            if not has_boundaries or current is None:
                flush()
                current = {
                    "sourceId": event.get("sourceId"),
                    "sourceRange": event.get("sourceRange"),
                    "heading": "",
                    "viewpoints": [],
                    "images": [],
                }
            for point in event["points"]:
                key = re.sub(r"\W+", "", point)
                if key in seen_points:
                    continue
                seen_points.add(key)
                current["viewpoints"].append(point)
        else:
            if current is None:
                current = {"sourceId": "", "sourceRange": "", "heading": "", "viewpoints": [], "images": []}
            current["images"].append(event["relativePath"])

    flush()
    return sections


def write_sheet_md(path: Path, title: str, sections: list[dict[str, Any]]) -> None:
    lines: list[str] = [f"# {title}", ""]
    for section in sections:
        if section["viewpoints"]:
            lines.extend(["## 观点文字资产", ""])
            for point in section["viewpoints"]:
                lines.append(f"- {point}")
            lines.append("")
        if section["images"]:
            lines.extend(["## 图片资产", ""])
            for image in section["images"]:
                lines.append(f"- {image}")
            lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    manifest = read_json(args.manifest)
    manifest_dir = args.manifest.parent
    output_dir = args.output_dir or (manifest_dir / "sheet-md-assets")
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("*.md"):
        try:
            old_file.chmod(stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        try:
            old_file.unlink()
        except PermissionError:
            pass
    old_index = output_dir / "sheet-md-manifest.json"
    if old_index.exists():
        try:
            old_index.chmod(stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        try:
            old_index.unlink()
        except PermissionError:
            pass

    index: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for group_index, group in enumerate(manifest.get("contentGroups", []), start=1):
        if group.get("kind") == "metadata":
            continue
        title = group.get("title") or group.get("groupId") or group.get("sheet") or f"sheet-{group_index}"
        sections = build_sheet_sections(group, manifest_dir)
        if not sections:
            continue
        base = safe_filename(group.get("groupId") or title)
        filename = f"{base}.md"
        suffix = 2
        while filename in used_names:
            filename = f"{base}_{suffix}.md"
            suffix += 1
        used_names.add(filename)
        md_path = output_dir / filename
        write_sheet_md(md_path, title, sections)
        index.append(
            {
                "order": len(index) + 1,
                "groupId": group.get("groupId"),
                "sheet": group.get("sheet"),
                "title": title,
                "markdown": str(md_path.relative_to(manifest_dir)).replace("\\", "/"),
                "sectionCount": len(sections),
                "viewpointCount": sum(len(section["viewpoints"]) for section in sections),
                "imageCount": sum(len(section["images"]) for section in sections),
            }
        )

    manifest_out = {
        "version": 1,
        "sourceManifest": str(args.manifest),
        "outputDir": str(output_dir),
        "sheetCount": len(index),
        "sheets": index,
    }
    try:
        (output_dir / "sheet-md-manifest.json").write_text(
            json.dumps(manifest_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except PermissionError:
        pass

    if args.pretty:
        print(json.dumps({"sheetCount": len(index), "sheets": index}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
