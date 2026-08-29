#!/usr/bin/env python
"""Step 3B PPTX composer.

This is the default offline composer for the skill. It edits the PPTX OOXML
package directly, clones template slides, and adds Step 3A planned content
without requiring PowerPoint, WPS, Office COM, or a graphical desktop session.
"""

from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree
from PIL import Image


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}

EMU_PER_PX = 9525
SLIDE_W = 1280
SLIDE_H = 720
RED = "B00020"
DEEP_RED = "8C001A"
GOLD = "C5A15A"
TEXT = "111111"
MUTED = "666666"
PALE_RED = "F4E6E8"
WHITE = "FFFFFF"
LIGHT_GRAY = "F2F2F2"
CONTENT_TOP = 122
CONTENT_BOTTOM = 632
SUMMARY_X = 60
SUMMARY_Y = 122
SUMMARY_W = 1130
SUMMARY_H = 180
SUMMARY_H_TALL = 350
SUMMARY_W_WITH_SIDE_IMAGE = 675
SUMMARY_H_WITH_SIDE_IMAGE = 235
SUMMARY_TEXT_X = 102
SUMMARY_TEXT_Y = 134
SUMMARY_TEXT_W = 1072
SUMMARY_TEXT_W_WITH_SIDE_IMAGE = 617
SUMMARY_PAD_BOTTOM = 24
MIN_SUMMARY_FONT = 8
DEFAULT_SUMMARY_FONT = 12
DEFAULT_TEXT_ONLY_FONT = 15


@dataclass
class Frame:
    left: float
    top: float
    width: float
    height: float


def px(value: float) -> str:
    return str(int(round(value * EMU_PER_PX)))


def qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def e(prefix: str, tag: str, attrib: dict[str, str] | None = None, *children: etree._Element) -> etree._Element:
    elem = etree.Element(qn(prefix, tag), attrib or {})
    for child in children:
        elem.append(child)
    return elem


def parse_xml(data: bytes) -> etree._Element:
    return etree.fromstring(data)


def serialize_xml(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_zip_entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def save_zip_entries(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(entries):
            zf.writestr(name, entries[name])


def max_shape_id(slide_root: etree._Element) -> int:
    values = []
    for node in slide_root.xpath(".//p:cNvPr", namespaces=NS):
        raw = node.get("id")
        if raw and raw.isdigit():
            values.append(int(raw))
    return max(values or [1])


def next_rel_id(rels_root: etree._Element) -> str:
    max_id = 0
    for rel in rels_root.xpath("./rel:Relationship", namespaces=NS):
        rid = rel.get("Id", "")
        match = re.fullmatch(r"rId(\d+)", rid)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"rId{max_id + 1}"


def strip_duplicate_sensitive_rels(rels_root: etree._Element) -> None:
    """Remove slide-private metadata relationships before reusing a slide part.

    Notes, comments, and slide tags often point back to a specific source slide.
    Reusing them across many duplicated slides can make PowerPoint treat the
    output package as inconsistent even when every target file exists.
    """
    sensitive_suffixes = ("/notesSlide", "/comments", "/tags")
    for rel in list(rels_root):
        rel_type = rel.get("Type", "")
        if rel_type.endswith(sensitive_suffixes):
            rels_root.remove(rel)


def strip_chart_shapes_and_rels(slide_root: etree._Element, rels_root: etree._Element) -> int:
    """Remove inherited chart objects from cloned slides.

    The source template contains sample chart parts. Duplicating content pages
    while leaving all copies pointed at the same chart part can make PowerPoint
    reject the generated deck. Step 3B inserts planned PNG visuals, so inherited
    chart objects are not needed in the MVP output.
    """
    chart_rids = set(slide_root.xpath(".//c:chart/@r:id", namespaces=NS))
    removed_shapes = 0
    for graphic_frame in list(slide_root.xpath(".//p:graphicFrame[.//c:chart]", namespaces=NS)):
        parent = graphic_frame.getparent()
        if parent is not None:
            parent.remove(graphic_frame)
            removed_shapes += 1

    for rel in list(rels_root):
        rel_type = rel.get("Type", "")
        if rel.get("Id") in chart_rids or rel_type.endswith("/chart"):
            rels_root.remove(rel)
    return removed_shapes


def strip_slide_private_exts(slide_root: etree._Element) -> int:
    """Remove duplicated slide-private IDs from cloned slide XML.

    PowerPoint can reject decks when many cloned slides retain identical
    creationId/modId extension values from a source slide.
    """
    removed = 0
    for node in list(slide_root.xpath(".//*[local-name()='creationId' or local-name()='modId']")):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
            removed += 1
    for ext in list(slide_root.xpath(".//*[local-name()='extLst']/*[local-name()='ext']")):
        if len(ext) == 0 and not (ext.text or "").strip():
            parent = ext.getparent()
            if parent is not None:
                parent.remove(ext)
    for ext_lst in list(slide_root.xpath(".//*[local-name()='extLst']")):
        if len(ext_lst) == 0 and not (ext_lst.text or "").strip():
            parent = ext_lst.getparent()
            if parent is not None:
                parent.remove(ext_lst)
    return removed


def ensure_slide_rels(entries: dict[str, bytes], slide_no: int) -> etree._Element:
    rel_path = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
    if rel_path in entries:
        return parse_xml(entries[rel_path])
    return etree.Element(qn("rel", "Relationships"), nsmap={None: NS["rel"]})


def xfrm(frame: Frame) -> etree._Element:
    return e("a", "xfrm", None, e("a", "off", {"x": px(frame.left), "y": px(frame.top)}), e("a", "ext", {"cx": px(frame.width), "cy": px(frame.height)}))


def solid_fill(color: str) -> etree._Element:
    return e("a", "solidFill", None, e("a", "srgbClr", {"val": color}))


def no_line() -> etree._Element:
    return e("a", "ln", None, e("a", "noFill"))


def shape_xml(
    shape_id: int,
    name: str,
    frame: Frame,
    *,
    geom: str = "rect",
    fill: str | None = None,
    line: str | None = None,
    text: str | None = None,
    font_size: int = 18,
    color: str = TEXT,
    bold: bool = False,
    align: str = "l",
    valign: str = "t",
    bullet: bool = False,
) -> etree._Element:
    valign = {"mid": "ctr", "center": "ctr", "middle": "ctr"}.get(valign, valign)
    sp = e("p", "sp")
    nv = e(
        "p",
        "nvSpPr",
        None,
        e("p", "cNvPr", {"id": str(shape_id), "name": name}),
        e("p", "cNvSpPr", {"txBox": "1" if text is not None else "0"}),
        e("p", "nvPr"),
    )
    sp.append(nv)

    sp_pr = e("p", "spPr", None, xfrm(frame), e("a", "prstGeom", {"prst": geom}, e("a", "avLst")))
    if fill:
        sp_pr.append(solid_fill(fill))
    else:
        sp_pr.append(e("a", "noFill"))
    if line:
        sp_pr.append(e("a", "ln", {"w": "6350"}, solid_fill(line)))
    else:
        sp_pr.append(no_line())
    sp.append(sp_pr)

    if text is not None:
        body_pr = e(
            "a",
            "bodyPr",
            {"wrap": "square", "anchor": valign, "lIns": "0", "rIns": "0", "tIns": "0", "bIns": "0"},
        )
        body_pr.append(e("a", "noAutofit"))
        tx_body = e("p", "txBody", None, body_pr, e("a", "lstStyle"))
        paragraphs = text.splitlines() or [""]
        for para in paragraphs:
            p_elem = e("a", "p")
            p_pr = e("a", "pPr", {"algn": align})
            if bullet:
                p_pr.set("marL", px(18))
                p_pr.set("indent", px(-10))
                p_pr.append(e("a", "buChar", {"char": "•"}))
            p_elem.append(p_pr)
            r_pr = e(
                "a",
                "rPr",
                {"lang": "zh-CN", "sz": str(font_size * 100), "b": "1" if bold else "0"},
                solid_fill(color),
                e("a", "latin", {"typeface": "Microsoft YaHei"}),
                e("a", "ea", {"typeface": "Microsoft YaHei"}),
            )
            run = e("a", "r", None, r_pr, e("a", "t"))
            run.find("a:t", namespaces=NS).text = para
            p_elem.append(run)
            tx_body.append(p_elem)
        sp.append(tx_body)
    return sp


def pic_xml(shape_id: int, name: str, frame: Frame, rid: str) -> etree._Element:
    pic = e("p", "pic")
    pic.append(
        e(
            "p",
            "nvPicPr",
            None,
            e("p", "cNvPr", {"id": str(shape_id), "name": name}),
            e("p", "cNvPicPr", None, e("a", "picLocks", {"noChangeAspect": "1"})),
            e("p", "nvPr"),
        )
    )
    blip = e("a", "blip")
    blip.set(qn("r", "embed"), rid)
    pic.append(e("p", "blipFill", None, blip, e("a", "stretch", None, e("a", "fillRect"))))
    pic.append(
        e(
            "p",
            "spPr",
            None,
            xfrm(frame),
            e("a", "prstGeom", {"prst": "rect"}, e("a", "avLst")),
            e("a", "ln", {"w": "6350"}, solid_fill("D9D9D9")),
        )
    )
    return pic


def append_shape(sp_tree: etree._Element, shape: etree._Element) -> None:
    ext_lst = sp_tree.find("p:extLst", namespaces=NS)
    if ext_lst is not None:
        sp_tree.insert(list(sp_tree).index(ext_lst), shape)
    else:
        sp_tree.append(shape)


def shape_text(shape: etree._Element) -> str:
    return normalize_text("".join(node.text or "" for node in shape.xpath(".//a:t", namespaces=NS)))


def shape_name(shape: etree._Element) -> str:
    node = shape.find(".//p:cNvPr", namespaces=NS)
    return node.get("name", "") if node is not None else ""


def set_shape_text(shape: etree._Element, text: str) -> None:
    text_nodes = shape.xpath(".//a:t", namespaces=NS)
    if not text_nodes:
        return
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        node.text = ""


def text_shapes(sp_tree: etree._Element) -> list[etree._Element]:
    return [shape for shape in sp_tree.findall("p:sp", namespaces=NS) if shape_text(shape)]


def remove_shape(shape: etree._Element) -> None:
    parent = shape.getparent()
    if parent is not None:
        parent.remove(shape)


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "image/png"


def image_frame(path: Path, frame: Frame) -> Frame:
    try:
        with Image.open(path) as img:
            w, h = img.size
    except Exception:
        return frame
    if w <= 0 or h <= 0:
        return frame
    scale = min(frame.width / w, frame.height / h)
    actual_w = w * scale
    actual_h = h * scale
    return Frame(frame.left + (frame.width - actual_w) / 2, frame.top + (frame.height - actual_h) / 2, actual_w, actual_h)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def slide_text(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_text(value.get("displayText") or value.get("text") or value.get("sourceText"))
    return normalize_text(value)


def compact_visible_text(text: str, max_chars: int) -> str:
    return normalize_text(text)


def short_bullets(slide: dict[str, Any], max_count: int = 4) -> list[str]:
    bullets = []
    for item in slide.get("content", {}).get("bullets", []):
        text = slide_text(item)
        if not text:
            continue
        bullets.append(text)
    return bullets


def visual_paths(slide: dict[str, Any], project_dir: Path | None = None) -> list[dict[str, Any]]:
    items = []
    for visual in slide.get("content", {}).get("visualAssets", []):
        raw = visual.get("absolutePath") or visual.get("selectedVisualPath") or visual.get("path") or visual.get("relativePath")
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute() and project_dir is not None:
            path = project_dir / path
        if path.exists():
            items.append({"path": path, "title": normalize_text(visual.get("captionText") or visual.get("title"))})
    return items


def add_image_to_slide(
    entries: dict[str, bytes],
    rels_root: etree._Element,
    sp_tree: etree._Element,
    slide_no: int,
    image_no: int,
    shape_id: int,
    path: Path,
    frame: Frame,
) -> None:
    ext = path.suffix.lower() or ".png"
    media_name = f"ppt/media/step3b_s{slide_no:03d}_v{image_no:02d}{ext}"
    entries[media_name] = path.read_bytes()
    rid = next_rel_id(rels_root)
    rel = e(
        "rel",
        "Relationship",
        {
            "Id": rid,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            "Target": f"../media/{Path(media_name).name}",
        },
    )
    rels_root.append(rel)
    append_shape(sp_tree, pic_xml(shape_id, f"step3b-image-{slide_no}-{image_no}", image_frame(path, frame), rid))


def add_cover(slide: dict[str, Any], sp_tree: etree._Element, shape_id: int) -> int:
    title = normalize_text(slide.get("content", {}).get("title") or slide.get("title"))
    date = normalize_text(slide.get("content", {}).get("date")) or "2026年7月"
    if " 国泰基金" in title:
        main_title, fund_title = title.split(" 国泰基金", 1)
        fund_title = "国泰基金" + fund_title
    else:
        main_title, fund_title = title, ""
    for shape in text_shapes(sp_tree):
        current = shape_text(shape)
        if "2026年" in current or "2023年" in current:
            set_shape_text(shape, date)
        elif "中国银行" in current or "企业年金" in current:
            set_shape_text(shape, main_title)
        elif "国泰基金" in current or "投资汇报" in current:
            set_shape_text(shape, fund_title or title)
    return shape_id


def add_toc(slide: dict[str, Any], sp_tree: etree._Element, shape_id: int) -> int:
    items = slide.get("content", {}).get("items", [])
    titles = [normalize_text(item.get("title")) for item in items]
    indices = [normalize_text(item.get("index")) for item in items]
    title_cursor = 0
    index_cursor = 0
    for shape in text_shapes(sp_tree):
        current = shape_text(shape)
        if "灯片编号" in shape_name(shape):
            continue
        if current.isdigit() and len(current) <= 2 and index_cursor < len(indices):
            set_shape_text(shape, indices[index_cursor])
            index_cursor += 1
        elif current not in {"目录", "Contents"} and title_cursor < len(titles):
            set_shape_text(shape, titles[title_cursor])
            title_cursor += 1
    return shape_id


def add_section(slide: dict[str, Any], sp_tree: etree._Element, shape_id: int) -> int:
    content = slide.get("content", {})
    idx = normalize_text(content.get("sectionIndex"))
    title = normalize_text(content.get("sectionTitle") or slide.get("title"))
    for shape in text_shapes(sp_tree):
        current = shape_text(shape)
        if "灯片编号" in shape_name(shape):
            continue
        if current.isdigit() and len(current) <= 2:
            set_shape_text(shape, idx)
        elif "灯片编号" not in shape_name(shape):
            set_shape_text(shape, title)
    return shape_id


def shape_bounds(shape: etree._Element) -> Frame | None:
    xfrm_node = shape.find(".//a:xfrm", namespaces=NS)
    if xfrm_node is None:
        return None
    off = xfrm_node.find("a:off", namespaces=NS)
    ext = xfrm_node.find("a:ext", namespaces=NS)
    if off is None or ext is None:
        return None
    return Frame(
        int(off.get("x", "0")) / EMU_PER_PX,
        int(off.get("y", "0")) / EMU_PER_PX,
        int(ext.get("cx", "0")) / EMU_PER_PX,
        int(ext.get("cy", "0")) / EMU_PER_PX,
    )


def intersects_content_area(frame: Frame | None) -> bool:
    if frame is None:
        return False
    return frame.top + frame.height > CONTENT_TOP and frame.top < CONTENT_BOTTOM


def is_slide_number_shape(shape: etree._Element) -> bool:
    name = shape_name(shape)
    text = shape_text(shape)
    return "灯片编号" in name or "Slide Number" in name or (text.isdigit() and shape_bounds(shape) is None)


def is_title_shape(shape: etree._Element) -> bool:
    name = shape_name(shape)
    bounds = shape_bounds(shape)
    text = shape_text(shape)
    if "标题" in name or "Title" in name:
        return True
    return bool(text and bounds and bounds.top < 115 and bounds.width > 700)


def image_grid_frames(count: int, has_bullets: bool) -> list[Frame]:
    if count <= 0:
        return []
    if count == 1:
        if has_bullets:
            return [Frame(60, 335, 1130, 260)]
        return [Frame(60, 120, 1130, 490)]
    if count == 2:
        if has_bullets:
            return [Frame(60, 335, 550, 260), Frame(640, 335, 550, 260)]
        return [Frame(60, 125, 550, 440), Frame(640, 125, 550, 440)]
    return [
        Frame(760, 120, 430, 235),
        Frame(60, 385, 550, 225),
        Frame(640, 385, 550, 225),
    ]


def summary_frames(visual_count: int, has_bullets: bool) -> tuple[Frame | None, Frame | None, int, int]:
    if not has_bullets:
        return None, None, DEFAULT_SUMMARY_FONT, MIN_SUMMARY_FONT
    if visual_count >= 3:
        return (
            Frame(SUMMARY_X, SUMMARY_Y, SUMMARY_W_WITH_SIDE_IMAGE, SUMMARY_H_WITH_SIDE_IMAGE),
            Frame(SUMMARY_TEXT_X, SUMMARY_TEXT_Y, SUMMARY_TEXT_W_WITH_SIDE_IMAGE, SUMMARY_H_WITH_SIDE_IMAGE - SUMMARY_PAD_BOTTOM),
            DEFAULT_SUMMARY_FONT,
            MIN_SUMMARY_FONT,
        )
    if visual_count >= 1:
        return (
            Frame(SUMMARY_X, SUMMARY_Y, SUMMARY_W, SUMMARY_H),
            Frame(SUMMARY_TEXT_X, SUMMARY_TEXT_Y, SUMMARY_TEXT_W, SUMMARY_H - SUMMARY_PAD_BOTTOM),
            DEFAULT_SUMMARY_FONT,
            MIN_SUMMARY_FONT,
        )
    return (
        Frame(SUMMARY_X, SUMMARY_Y, SUMMARY_W, SUMMARY_H_TALL),
        Frame(SUMMARY_TEXT_X, SUMMARY_TEXT_Y, SUMMARY_TEXT_W, SUMMARY_H_TALL - SUMMARY_PAD_BOTTOM),
        DEFAULT_TEXT_ONLY_FONT,
        MIN_SUMMARY_FONT,
    )


def clean_content_template(sp_tree: etree._Element, title: str) -> None:
    title_shape: etree._Element | None = None
    for shape in list(sp_tree.findall("p:sp", namespaces=NS)):
        name = shape_name(shape)
        if is_slide_number_shape(shape):
            continue
        if title_shape is None and is_title_shape(shape):
            title_shape = shape
            continue
        bounds = shape_bounds(shape)
        text = shape_text(shape)
        if name.startswith("step3b-") or text or (not text and intersects_content_area(bounds)):
            remove_shape(shape)
    if title_shape is not None:
        set_shape_text(title_shape, title)
    for node in list(sp_tree.findall("p:graphicFrame", namespaces=NS)):
        remove_shape(node)
    for node in list(sp_tree.findall("p:pic", namespaces=NS)):
        name = shape_name(node)
        bounds = shape_bounds(node)
        if name.startswith("step3b-") or intersects_content_area(bounds):
            remove_shape(node)


def update_slide_number(sp_tree: etree._Element, slide_no: int) -> None:
    for shape in text_shapes(sp_tree):
        if "灯片编号" in shape_name(shape):
            set_shape_text(shape, str(slide_no))


def text_unit_width(text: str) -> float:
    total = 0.0
    for char in text:
        code = ord(char)
        if char.isspace():
            total += 0.3
        elif 0x4E00 <= code <= 0x9FFF or 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            total += 1.0
        elif char.isdigit() or char.isascii():
            total += 0.55
        else:
            total += 0.8
    return total


def estimated_line_count(text: str, width: float, font_size: int) -> int:
    units_per_line = max(1.0, width / (font_size * 1.14))
    return max(1, int((text_unit_width(text) + units_per_line - 0.01) // units_per_line))


def line_height(font_size: int) -> float:
    return 1.75 * font_size


def fit_bullet_layout(bullets: list[str], frame: Frame, max_font: int, min_font: int) -> dict[str, Any] | None:
    if not bullets:
        return {"fontSize": max_font, "placements": [], "usedHeight": 0.0}
    for font_size in range(max_font, min_font - 1, -1):
        y = frame.top
        gap = 12.6 * (font_size / 12)
        dot_size = 12 if font_size >= 14 else 10
        placements = []
        fits = True
        for index, bullet in enumerate(bullets, start=1):
            lines = estimated_line_count(bullet, frame.width, font_size)
            height = max(line_height(font_size), lines * line_height(font_size))
            if y + height > frame.top + frame.height:
                fits = False
                break
            placements.append(
                {
                    "index": index,
                    "text": bullet,
                    "textFrame": Frame(frame.left, y, frame.width, height),
                    "dotFrame": Frame(78, y + (line_height(font_size) - dot_size) / 2, dot_size, dot_size),
                    "lines": lines,
                }
            )
            y += height + gap
        if fits:
            return {"fontSize": font_size, "placements": placements, "usedHeight": y - frame.top - gap}
    return None


def split_text_to_fit(text: str, frame: Frame, max_font: int, min_font: int) -> list[str]:
    text = normalize_text(text)
    if fit_bullet_layout([text], frame, max_font, min_font):
        return [text]
    tokens = [part for part in re.findall(r".+?[。！？；;.!?，,、]\s*|.+?$", text) if part]
    if len(tokens) <= 1:
        tokens = list(text)
    chunks: list[str] = []
    remaining = tokens[:]
    while remaining:
        best = ""
        best_count = 0
        for count in range(1, len(remaining) + 1):
            candidate = normalize_text("".join(remaining[:count]))
            if fit_bullet_layout([candidate], frame, max_font, min_font):
                best = candidate
                best_count = count
            else:
                break
        if best_count == 0:
            best = normalize_text(str(remaining[0]))
            best_count = 1
        chunks.append(best)
        remaining = remaining[best_count:]
    return chunks


def paginate_bullets(bullets: list[str], first_visual_count: int) -> list[list[str]]:
    pages: list[list[str]] = []
    remaining = bullets[:]
    page_index = 0
    guard = 0
    while remaining:
        guard += 1
        if guard > 200:
            raise RuntimeError("Text pagination guard tripped; check unusually long slide content.")
        visual_count = first_visual_count if page_index == 0 else 0
        _, text_frame, max_font, min_font = summary_frames(visual_count, True)
        if text_frame is None:
            pages.append(remaining)
            break
        best_count = 0
        for count in range(1, len(remaining) + 1):
            if fit_bullet_layout(remaining[:count], text_frame, max_font, min_font):
                best_count = count
            else:
                break
        if best_count == 0:
            split = split_text_to_fit(remaining[0], text_frame, max_font, min_font)
            remaining = split + remaining[1:]
            continue
        pages.append(remaining[:best_count])
        remaining = remaining[best_count:]
        page_index += 1
    return pages


def add_summary_boxes(
    sp_tree: etree._Element,
    shape_id: int,
    bullets: list[str],
    visual_count: int,
) -> tuple[int, dict[str, Any]]:
    summary_frame, text_frame, max_font, min_font = summary_frames(visual_count, bool(bullets))
    if summary_frame is None or text_frame is None:
        return shape_id, {"bulletCount": 0, "fontSize": None, "textOverflow": False}
    append_shape(sp_tree, shape_xml(shape_id, "step3b-summary-bg", summary_frame, fill=LIGHT_GRAY))
    shape_id += 1
    fit = fit_bullet_layout(bullets, text_frame, max_font, min_font)
    overflow = fit is None
    if fit is None:
        fit = fit_bullet_layout(bullets[:1], text_frame, min_font, min_font) or {"fontSize": min_font, "placements": [], "usedHeight": 0}
    for placement in fit["placements"]:
        append_shape(sp_tree, shape_xml(shape_id, f"step3b-summary-dot-{placement['index']}", placement["dotFrame"], geom="ellipse", fill=RED))
        shape_id += 1
        append_shape(
            sp_tree,
            shape_xml(
                shape_id,
                f"step3b-summary-text-{placement['index']}",
                placement["textFrame"],
                text=placement["text"],
                font_size=int(fit["fontSize"]),
                color="000000",
            ),
        )
        shape_id += 1
    return shape_id, {
        "bulletCount": len(bullets),
        "fontSize": fit["fontSize"],
        "usedHeight": round(float(fit.get("usedHeight", 0.0)), 2),
        "textOverflow": overflow,
    }


def content_bullets(slide: dict[str, Any], visual_count: int) -> list[str]:
    return short_bullets(slide, max_count=999)


def add_content(
    entries: dict[str, bytes],
    rels_root: etree._Element,
    slide: dict[str, Any],
    slide_no: int,
    sp_tree: etree._Element,
    shape_id: int,
    project_dir: Path | None = None,
) -> tuple[int, list[str], dict[str, Any]]:
    added = []
    title = normalize_text(slide.get("title"))
    visuals = visual_paths(slide, project_dir)
    visual_limit = min(len(visuals), 3)
    bullets = content_bullets(slide, visual_limit)
    clean_content_template(sp_tree, title)

    layout_report: dict[str, Any] = {
        "layout": "summary_plus_chart_grid",
        "visualCount": visual_limit,
        "bulletCount": len(bullets),
        "textOverflow": False,
    }
    if bullets:
        shape_id, text_report = add_summary_boxes(sp_tree, shape_id, bullets, visual_limit)
        layout_report.update(text_report)

    frames = image_grid_frames(visual_limit, bool(bullets))
    for index, (visual, frame) in enumerate(zip(visuals[:visual_limit], frames), start=1):
        shape_id += 1
        add_image_to_slide(entries, rels_root, sp_tree, slide_no, index, shape_id, visual["path"], frame)
        added.append(str(visual["path"]))

    if not bullets and not visuals:
        append_shape(sp_tree, shape_xml(shape_id, "step3b-empty-note", Frame(110, 170, 980, 80), text="本页内容待补充。", font_size=22, color=MUTED))
        shape_id += 1
    return shape_id, added, layout_report


def add_role_content(
    entries: dict[str, bytes],
    rels_root: etree._Element,
    slide_root: etree._Element,
    slide: dict[str, Any],
    slide_no: int,
    project_dir: Path | None = None,
) -> dict[str, Any]:
    sp_tree = slide_root.find(".//p:cSld/p:spTree", namespaces=NS)
    if sp_tree is None:
        raise ValueError(f"slide {slide_no} has no spTree")
    shape_id = max_shape_id(slide_root) + 1
    role = slide.get("role")
    added_images: list[str] = []
    layout_report: dict[str, Any] = {}
    update_slide_number(sp_tree, slide_no)
    if role == "cover":
        shape_id = add_cover(slide, sp_tree, shape_id)
    elif role == "toc":
        shape_id = add_toc(slide, sp_tree, shape_id)
    elif role == "section":
        shape_id = add_section(slide, sp_tree, shape_id)
    elif role == "content":
        shape_id, added_images, layout_report = add_content(entries, rels_root, slide, slide_no, sp_tree, shape_id, project_dir)
    return {"role": role, "shapeIdEnd": shape_id, "addedImages": added_images, **layout_report}


def update_content_types(entries: dict[str, bytes], slide_count: int, media_paths: list[str]) -> None:
    root = parse_xml(entries["[Content_Types].xml"])
    for child in list(root):
        if child.tag == qn("ct", "Override") and child.get("PartName", "").startswith("/ppt/slides/slide"):
            root.remove(child)
    for i in range(1, slide_count + 1):
        root.append(
            e(
                "ct",
                "Override",
                {
                    "PartName": f"/ppt/slides/slide{i}.xml",
                    "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
                },
            )
        )
    existing_defaults = {child.get("Extension") for child in root if child.tag == qn("ct", "Default")}
    for media in media_paths:
        ext = Path(media).suffix.lower().lstrip(".")
        if ext and ext not in existing_defaults:
            root.insert(0, e("ct", "Default", {"Extension": ext, "ContentType": content_type_for(Path(media))}))
            existing_defaults.add(ext)
    entries["[Content_Types].xml"] = serialize_xml(root)


def update_presentation_relationships(entries: dict[str, bytes], slide_count: int) -> None:
    pres_root = parse_xml(entries["ppt/presentation.xml"])
    for ext_lst in list(pres_root.xpath("./p:extLst", namespaces=NS)):
        pres_root.remove(ext_lst)
    for custom_data in list(pres_root.xpath("./p:custDataLst", namespaces=NS)):
        pres_root.remove(custom_data)

    sld_id_lst = pres_root.find("p:sldIdLst", namespaces=NS)
    if sld_id_lst is None:
        sld_id_lst = e("p", "sldIdLst")
        pres_root.insert(0, sld_id_lst)
    existing_slide_ids = []
    existing_slide_rids = []
    for child in list(sld_id_lst):
        raw_id = child.get("id")
        if raw_id and raw_id.isdigit():
            existing_slide_ids.append(int(raw_id))
        raw_rid = child.get(qn("r", "id"))
        if raw_rid:
            existing_slide_rids.append(raw_rid)
    for child in list(sld_id_lst):
        sld_id_lst.remove(child)
    next_slide_id = max(existing_slide_ids or [255]) + 1

    rel_root = parse_xml(entries["ppt/_rels/presentation.xml.rels"])
    max_rid = 0
    for rel in rel_root:
        match = re.fullmatch(r"rId(\d+)", rel.get("Id", ""))
        if match:
            max_rid = max(max_rid, int(match.group(1)))
    first_slide_rid = max_rid + 1

    for i in range(1, slide_count + 1):
        node = e("p", "sldId", {"id": str(next_slide_id + i - 1)})
        node.set(qn("r", "id"), f"rId{first_slide_rid + i - 1}")
        sld_id_lst.append(node)
    entries["ppt/presentation.xml"] = serialize_xml(pres_root)

    for rel in list(rel_root):
        rel_type = rel.get("Type", "")
        if rel_type == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" or rel_type.endswith("/tags"):
            rel_root.remove(rel)
    for i in range(1, slide_count + 1):
        rel_root.append(
            e(
                "rel",
                "Relationship",
                {
                    "Id": f"rId{first_slide_rid + i - 1}",
                    "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                    "Target": f"slides/slide{i}.xml",
                },
            )
        )
    entries["ppt/_rels/presentation.xml.rels"] = serialize_xml(rel_root)


def update_app_properties(entries: dict[str, bytes], plan: dict[str, Any]) -> None:
    path = "docProps/app.xml"
    if path not in entries:
        return
    root = parse_xml(entries[path])
    slide_count = len(plan.get("slides", []))
    slides_node = root.find("ep:Slides", namespaces=NS)
    if slides_node is not None:
        slides_node.text = str(slide_count)
    heading_pairs = root.find("ep:HeadingPairs/vt:vector", namespaces=NS)
    if heading_pairs is not None:
        variants = heading_pairs.findall("vt:variant", namespaces=NS)
        for index, variant in enumerate(variants[:-1]):
            text_node = variant.find("vt:lpstr", namespaces=NS)
            if text_node is not None and "幻灯片标题" in (text_node.text or ""):
                count_node = variants[index + 1].find("vt:i4", namespaces=NS)
                if count_node is not None:
                    count_node.text = str(slide_count)
    titles_vector = root.find("ep:TitlesOfParts/vt:vector", namespaces=NS)
    if titles_vector is not None:
        existing = [node.text or "" for node in titles_vector.findall("vt:lpstr", namespaces=NS)]
        non_slide_count = max(0, len(existing) - 18)
        base_titles = existing[:non_slide_count]
        slide_titles = [normalize_text(slide.get("title")) or f"Slide {idx}" for idx, slide in enumerate(plan.get("slides", []), start=1)]
        for child in list(titles_vector):
            titles_vector.remove(child)
        titles_vector.set("size", str(len(base_titles) + len(slide_titles)))
        for title in base_titles + slide_titles:
            titles_vector.append(e("vt", "lpstr"))
            titles_vector[-1].text = title
    entries[path] = serialize_xml(root)


def clone_slide_with_content(slide: dict[str, Any], bullets: list[str], visuals: list[Any], page_index: int, page_count: int) -> dict[str, Any]:
    cloned = copy.deepcopy(slide)
    content = cloned.setdefault("content", {})
    content["bullets"] = bullets
    content["visualAssets"] = visuals
    if page_count > 1:
        cloned["continuationIndex"] = page_index + 1
        cloned["continuationCount"] = page_count
        cloned["continuationOfSlideId"] = slide.get("slideId")
    return cloned


def expand_content_slide(slide: dict[str, Any]) -> list[dict[str, Any]]:
    content = slide.get("content", {})
    bullets = [slide_text(item) for item in content.get("bullets", []) if slide_text(item)]
    visuals = content.get("visualAssets", [])
    if not bullets:
        if len(visuals) <= 3:
            return [copy.deepcopy(slide)]
        pages = []
        visual_chunks = [visuals[index : index + 3] for index in range(0, len(visuals), 3)]
        for index, chunk in enumerate(visual_chunks):
            pages.append(clone_slide_with_content(slide, [], chunk, index, len(visual_chunks)))
        return pages

    first_visuals = visuals[:3]
    bullet_pages = paginate_bullets(bullets, min(len(first_visuals), 3))
    pages = []
    page_count = len(bullet_pages)
    for index, page_bullets in enumerate(bullet_pages):
        pages.append(clone_slide_with_content(slide, page_bullets, first_visuals if index == 0 else [], index, page_count))
    extra_visuals = visuals[3:]
    if extra_visuals:
        for chunk in [extra_visuals[index : index + 3] for index in range(0, len(extra_visuals), 3)]:
            pages.append(clone_slide_with_content(slide, [], chunk, len(pages), len(pages) + 1))
    return pages


def expand_plan_for_pagination(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    expanded = copy.deepcopy(plan)
    expanded_slides = []
    split_details = []
    for original_index, slide in enumerate(plan.get("slides", []), start=1):
        if slide.get("role") == "content":
            slides = expand_content_slide(slide)
        else:
            slides = [copy.deepcopy(slide)]
        if len(slides) > 1:
            split_details.append(
                {
                    "originalSlide": original_index,
                    "title": slide.get("title"),
                    "outputPageCount": len(slides),
                    "reason": "text_or_visuals_exceeded_single_content_grid",
                }
            )
        expanded_slides.extend(slides)
    for index, slide in enumerate(expanded_slides, start=1):
        slide["slideNumber"] = index
    expanded["slides"] = expanded_slides
    return expanded, {
        "originalSlideCount": len(plan.get("slides", [])),
        "expandedSlideCount": len(expanded_slides),
        "splitSlideCount": len(split_details),
        "splits": split_details,
    }


def build_frame_map(plan: dict[str, Any], out_path: Path) -> dict[str, Any]:
    output_slides = []
    for idx, slide in enumerate(plan["slides"], start=1):
        template = slide.get("template", {})
        output_slides.append(
            {
                "outputSlide": idx,
                "sourceSlide": int(template.get("sourceSlide", idx)),
                "reuseMode": "duplicate-slide",
                "narrativeRole": slide.get("role", "content"),
                "slideId": slide.get("slideId"),
                "title": slide.get("title"),
                "editTargets": [],
            }
        )
    frame_map = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourcePptx": plan.get("template", {}).get("sourcePptx"),
        "slidePlan": str(out_path.parent.parent / ("ppt-generation-plan.json" if (out_path.parent.parent / "ppt-generation-plan.json").exists() else "slide-plan.json")),
        "outputSlides": output_slides,
    }
    write_json(out_path, frame_map)
    return frame_map


def slide_size_px(entries: dict[str, bytes]) -> tuple[float, float]:
    root = parse_xml(entries["ppt/presentation.xml"])
    node = root.find("p:sldSz", namespaces=NS)
    if node is None:
        return float(SLIDE_W), float(SLIDE_H)
    return int(node.get("cx", str(SLIDE_W * EMU_PER_PX))) / EMU_PER_PX, int(node.get("cy", str(SLIDE_H * EMU_PER_PX))) / EMU_PER_PX


def added_shape_overflows_px(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    slide_w, slide_h = slide_size_px(entries)
    issues = []
    for path, data in entries.items():
        match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", path)
        if not match:
            continue
        slide_no = int(match.group(1))
        root = parse_xml(data)
        for node in root.xpath(".//p:sp | .//p:pic", namespaces=NS):
            name = shape_name(node)
            if not name.startswith("step3b-"):
                continue
            bounds = shape_bounds(node)
            if bounds is None:
                continue
            if bounds.left < 0 or bounds.top < 0 or bounds.left + bounds.width > slide_w or bounds.top + bounds.height > slide_h:
                issues.append(
                    {
                        "slide": slide_no,
                        "name": name,
                        "left": round(bounds.left, 2),
                        "top": round(bounds.top, 2),
                        "width": round(bounds.width, 2),
                        "height": round(bounds.height, 2),
                    }
                )
    return sorted(issues, key=lambda item: (item["slide"], item["name"]))


def find_render_slides_script() -> Path | None:
    candidates = [
        Path.home()
        / ".codex"
        / "plugins"
        / "cache"
        / "openai-primary-runtime"
        / "presentations"
        / "26.630.12135"
        / "skills"
        / "presentations"
        / "container_tools"
        / "render_slides.py"
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    base = Path.home() / ".codex" / "plugins" / "cache" / "openai-primary-runtime" / "presentations"
    if base.exists():
        for candidate in base.glob("*/skills/presentations/container_tools/render_slides.py"):
            return candidate
    return None


def run_render_png_qa(
    pptx_path: Path,
    report_path: Path,
    entries: dict[str, bytes],
    slide_reports: list[dict[str, Any]],
    *,
    enabled: bool,
) -> dict[str, Any]:
    overflow_issues = added_shape_overflows_px(entries)
    text_overflow = [
        {"slide": item.get("outputSlide"), "title": item.get("title"), "fontSize": item.get("fontSize")}
        for item in slide_reports
        if item.get("textOverflow")
    ]
    result: dict[str, Any] = {
        "enabled": enabled,
        "renderSucceeded": False,
        "renderDir": None,
        "renderedPngCount": 0,
        "addedShapeOverflowCount": len(overflow_issues),
        "textOverflowCount": len(text_overflow),
        "issues": {
            "addedShapeOverflows": overflow_issues[:50],
            "textOverflows": text_overflow[:50],
        },
    }
    if not enabled:
        result["skipReason"] = "disabled_by_cli"
        return result
    script = find_render_slides_script()
    if script is None:
        result["skipReason"] = "render_slides.py_not_found"
        return result
    out_dir = (report_path.parent / f"{pptx_path.stem}-png-qa").resolve()
    tmp_dir = (report_path.parent / f"{pptx_path.stem}-render-tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    env["TMPDIR"] = str(tmp_dir)
    dependency_root = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    if dependency_root.exists():
        env["HOME"] = str(Path.home())
        env["CODEX_RUNTIME_DEPENDENCIES"] = str(dependency_root)
        env["CODEX_WORKSPACE_DEPENDENCIES"] = str(dependency_root)
        env["CODEX_DEPENDENCIES"] = str(dependency_root)
        env["NODE_PATH"] = str(dependency_root / "node" / "node_modules")
    wrapper = tmp_dir / "_render_slides_wrapper.py"
    wrapper.write_text(
        "\n".join(
            [
                "import runpy",
                "import os",
                "import sys",
                "import tempfile",
                "import uuid",
                f"tempfile.tempdir = {str(tmp_dir)!r}",
                "class _NoCleanupTemporaryDirectory:",
                "    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False):",
                "        base = dir or tempfile.tempdir",
                "        name = (prefix or 'tmp') + uuid.uuid4().hex + (suffix or '')",
                "        self.name = os.path.join(base, name)",
                "        os.makedirs(self.name, exist_ok=False)",
                "        os.chmod(self.name, 0o777)",
                "    def __enter__(self):",
                "        return self.name",
                "    def __exit__(self, exc_type, exc, tb):",
                "        return False",
                "    def cleanup(self):",
                "        return None",
                "tempfile.TemporaryDirectory = _NoCleanupTemporaryDirectory",
                f"sys.argv = [{str(script)!r}] + sys.argv[1:]",
                f"runpy.run_path({str(script)!r}, run_name='__main__')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(wrapper), str(pptx_path), "--output_dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
        env=env,
    )
    result["renderDir"] = str(out_dir)
    result["renderSucceeded"] = proc.returncode == 0
    result["renderedPngCount"] = len(list(out_dir.glob("*.png"))) if out_dir.exists() else 0
    if proc.returncode != 0:
        result["renderError"] = (proc.stderr or proc.stdout or "").strip()[:2000]
    return result


def compose(plan_path: Path, out_path: Path, frame_map_path: Path, report_path: Path, *, render_qa: bool = True) -> dict[str, Any]:
    plan = read_json(plan_path)
    output_plan, pagination_report = expand_plan_for_pagination(plan)
    project_dir = Path(plan.get("projectDir") or plan_path.parent)
    source_pptx = Path(plan["template"]["sourcePptx"])
    source_entries = load_zip_entries(source_pptx)
    entries = dict(source_entries)
    frame_map = build_frame_map(output_plan, frame_map_path)
    media_added: list[str] = []
    slide_reports = []

    for output in frame_map["outputSlides"]:
        out_no = int(output["outputSlide"])
        src_no = int(output["sourceSlide"])
        slide_xml_path = f"ppt/slides/slide{out_no}.xml"
        slide_rels_path = f"ppt/slides/_rels/slide{out_no}.xml.rels"
        src_xml_path = f"ppt/slides/slide{src_no}.xml"
        src_rels_path = f"ppt/slides/_rels/slide{src_no}.xml.rels"
        if src_xml_path not in source_entries:
            raise FileNotFoundError(f"Missing source slide part: {src_xml_path}")

        slide_root = copy.deepcopy(parse_xml(source_entries[src_xml_path]))
        rels_root = copy.deepcopy(parse_xml(source_entries[src_rels_path])) if src_rels_path in source_entries else ensure_slide_rels(source_entries, src_no)
        strip_duplicate_sensitive_rels(rels_root)
        removed_chart_shapes = strip_chart_shapes_and_rels(slide_root, rels_root)
        removed_private_exts = strip_slide_private_exts(slide_root)
        report = add_role_content(entries, rels_root, slide_root, output_plan["slides"][out_no - 1], out_no, project_dir)
        report["removedInheritedChartShapes"] = removed_chart_shapes
        report["removedSlidePrivateExtensions"] = removed_private_exts
        media_added.extend([f"ppt/media/{Path(path).name}" for path in report["addedImages"]])
        entries[slide_xml_path] = serialize_xml(slide_root)
        entries[slide_rels_path] = serialize_xml(rels_root)
        slide_reports.append({"outputSlide": out_no, "sourceSlide": src_no, "title": output.get("title"), **report})

    update_presentation_relationships(entries, len(output_plan["slides"]))
    update_content_types(entries, len(output_plan["slides"]), media_added)
    update_app_properties(entries, output_plan)
    save_zip_entries(out_path, entries)
    render_qa_report = run_render_png_qa(out_path, report_path, entries, slide_reports, enabled=render_qa)

    report = {
        "version": 1,
        "stage": "step_3b_ooxml_composer",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "compositionMode": "offline_ooxml",
        "note": "Generated without PowerPoint/WPS/Office COM by editing the PPTX package directly.",
        "slidePlan": str(plan_path),
        "templateFrameMap": str(frame_map_path),
        "sourcePptx": str(source_pptx),
        "outputPptx": str(out_path),
        "slideCount": len(output_plan["slides"]),
        "pagination": pagination_report,
        "renderQa": render_qa_report,
        "addedImageCount": sum(len(item["addedImages"]) for item in slide_reports),
        "visibleEllipsisCount": sum(
            1
            for slide in output_plan.get("slides", [])
            for bullet in slide.get("content", {}).get("bullets", [])
            if "..." in slide_text(bullet) or "…" in slide_text(bullet)
        ),
        "slides": slide_reports,
    }
    write_json(report_path, report)
    return report


def default_paths(project_dir: Path) -> tuple[Path, Path, Path, Path]:
    plan = project_dir / "ppt-generation-plan.json"
    if not plan.exists():
        plan = project_dir / "slide-plan.json"
    output_dir = project_dir / "output"
    stem = "fund-pension-annuity-step3b-draft"
    return (
        plan,
        output_dir / f"{stem}.pptx",
        output_dir / "template-frame-map.json",
        output_dir / "composition-report.json",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose Step 3B PPTX from ppt-generation-plan.json, falling back to slide-plan.json."
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        help="Project directory containing ppt-generation-plan.json or legacy slide-plan.json.",
    )
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--frame-map", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--skip-render-qa", action="store_true", help="Skip PNG rendering QA after writing the PPTX.")
    args = parser.parse_args()

    default_plan, default_out, default_frame_map, default_report = default_paths(args.project_dir)
    plan_path = args.plan or default_plan
    out_path = args.out or default_out
    frame_map_path = args.frame_map or default_frame_map
    report_path = args.report or default_report
    report = compose(plan_path, out_path, frame_map_path, report_path, render_qa=not args.skip_render_qa)
    print(json.dumps({"outputPptx": report["outputPptx"], "slideCount": report["slideCount"], "addedImageCount": report["addedImageCount"], "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

