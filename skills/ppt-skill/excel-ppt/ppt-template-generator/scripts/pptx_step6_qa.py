#!/usr/bin/env python
"""Step 6 QA checks for generated PPTX decks."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

EMU_PER_PX = 9525
DEFAULT_W = 1280
DEFAULT_H = 720
PLACEHOLDER_MARKERS = (
    "\u6b64\u5904\u6dfb\u52a0",
    "\u5355\u51fb\u6b64\u5904",
    "\u70b9\u51fb\u6b64\u5904",
    "Click to add",
)


def qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def parse_xml(data: bytes) -> etree._Element:
    return etree.fromstring(data)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def slide_size(entries: dict[str, bytes]) -> tuple[int, int]:
    root = parse_xml(entries["ppt/presentation.xml"])
    sld_sz = root.find("p:sldSz", namespaces=NS)
    if sld_sz is None:
        return DEFAULT_W * EMU_PER_PX, DEFAULT_H * EMU_PER_PX
    return int(sld_sz.get("cx", str(DEFAULT_W * EMU_PER_PX))), int(sld_sz.get("cy", str(DEFAULT_H * EMU_PER_PX)))


def relationship_target_exists(entries: dict[str, bytes], rels_path: str, target: str) -> bool:
    base = Path(rels_path).parent.parent
    normalized = posixpath.normpath(posixpath.join(base.as_posix(), target))
    return normalized in entries


def relationship_issues(entries: dict[str, bytes]) -> list[dict[str, str]]:
    issues = []
    for rels_path, data in entries.items():
        if not rels_path.endswith(".rels"):
            continue
        root = parse_xml(data)
        for rel in root.xpath("./rel:Relationship", namespaces=NS):
            target = rel.get("Target", "")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not relationship_target_exists(entries, rels_path, target):
                issues.append({"relsPath": rels_path, "relationshipId": rel.get("Id", ""), "target": target})
    return issues


def slide_paths(entries: dict[str, bytes]) -> list[str]:
    try:
        root = parse_xml(entries["ppt/presentation.xml"])
        rel_root = parse_xml(entries["ppt/_rels/presentation.xml.rels"])
        rel_targets = {
            rel.get("Id", ""): posixpath.normpath(posixpath.join("ppt", rel.get("Target", "")))
            for rel in rel_root.xpath("./rel:Relationship", namespaces=NS)
        }
        ordered: list[str] = []
        for sld_id in root.xpath("./p:sldIdLst/p:sldId", namespaces=NS):
            rid = sld_id.get(qn("r", "id"), "")
            target = rel_targets.get(rid, "")
            if target in entries:
                ordered.append(target)
        if ordered:
            return ordered
    except Exception:
        pass
    paths = [name for name in entries if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
    return sorted(paths, key=lambda value: int(re.search(r"slide(\d+)\.xml", value).group(1)))


def slide_texts(slide_root: etree._Element) -> list[str]:
    return [node.text or "" for node in slide_root.xpath(".//a:t", namespaces=NS)]


def placeholder_prompt_hits(entries: dict[str, bytes]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for part, data in entries.items():
        if not part.endswith(".xml"):
            continue
        if not part.startswith("ppt/slides/"):
            continue
        try:
            texts = slide_texts(parse_xml(data))
        except etree.XMLSyntaxError:
            continue
        for text in texts:
            if any(marker in text for marker in PLACEHOLDER_MARKERS):
                hits.append({"part": part, "text": text})
    return hits


def shape_name(node: etree._Element) -> str:
    c_nv_pr = node.find(".//p:cNvPr", namespaces=NS)
    return c_nv_pr.get("name", "") if c_nv_pr is not None else ""


def shape_text(node: etree._Element) -> str:
    return " ".join((item.text or "").strip() for item in node.xpath(".//a:t", namespaces=NS)).strip()


def xfrm_bounds(node: etree._Element) -> tuple[int, int, int, int] | None:
    xfrm = node.find(".//a:xfrm", namespaces=NS)
    if xfrm is None:
        return None
    off = xfrm.find("a:off", namespaces=NS)
    ext = xfrm.find("a:ext", namespaces=NS)
    if off is None or ext is None:
        return None
    x = int(off.get("x", "0"))
    y = int(off.get("y", "0"))
    cx = int(ext.get("cx", "0"))
    cy = int(ext.get("cy", "0"))
    return x, y, cx, cy


def incomplete_xfrm_shapes(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for slide_path in slide_paths(entries):
        slide_no = int(re.search(r"slide(\d+)\.xml", slide_path).group(1))
        root = parse_xml(entries[slide_path])
        for node in root.xpath(".//p:sp | .//p:pic", namespaces=NS):
            if node.find(".//p:ph", namespaces=NS) is not None:
                continue
            name = shape_name(node)
            text = shape_text(node)
            has_visible_payload = bool(text) or node.tag == qn("p", "pic")
            if not has_visible_payload:
                continue
            if xfrm_bounds(node) is None:
                issues.append(
                    {
                        "slide": slide_no,
                        "name": name,
                        "text": text[:80],
                        "missing": "transform_bounds",
                    }
                )
    return issues

def added_shape_overflows(entries: dict[str, bytes], slide_w: int, slide_h: int) -> list[dict[str, Any]]:
    overflows = []
    prefixes = ("step3b-", "step5-")
    for slide_path in slide_paths(entries):
        slide_no = int(re.search(r"slide(\d+)\.xml", slide_path).group(1))
        root = parse_xml(entries[slide_path])
        for node in root.xpath(".//p:sp | .//p:pic", namespaces=NS):
            name = shape_name(node)
            if not name.startswith(prefixes):
                continue
            bounds = xfrm_bounds(node)
            if bounds is None:
                continue
            x, y, cx, cy = bounds
            if x < 0 or y < 0 or x + cx > slide_w or y + cy > slide_h:
                overflows.append(
                    {
                        "slide": slide_no,
                        "name": name,
                        "x": x,
                        "y": y,
                        "cx": cx,
                        "cy": cy,
                    }
                )
    return overflows


def count_slide_images(entries: dict[str, bytes]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for slide_path in slide_paths(entries):
        slide_no = int(re.search(r"slide(\d+)\.xml", slide_path).group(1))
        root = parse_xml(entries[slide_path])
        counts[slide_no] = len(root.xpath(".//p:pic", namespaces=NS))
    return counts


def slide_layout_relationships(entries: dict[str, bytes]) -> list[int]:
    missing = []
    for slide_path in slide_paths(entries):
        slide_no = int(re.search(r"slide(\d+)\.xml", slide_path).group(1))
        rels_path = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
        if rels_path not in entries:
            missing.append(slide_no)
            continue
        root = parse_xml(entries[rels_path])
        has_layout = any((rel.get("Type", "").endswith("/slideLayout")) for rel in root.xpath("./rel:Relationship", namespaces=NS))
        if not has_layout:
            missing.append(slide_no)
    return missing


def planned_visual_count(plan: dict[str, Any]) -> int:
    return sum(
        len(slide.get("content", {}).get("visualAssets", []))
        for slide in plan.get("slides", [])
        if slide.get("role") == "content"
    )


def planned_visual_slides(plan: dict[str, Any]) -> list[int]:
    return [
        int(slide.get("slideNumber", index))
        for index, slide in enumerate(plan.get("slides", []), start=1)
        if slide.get("role") == "content" and slide.get("content", {}).get("visualAssets")
    ]


def composition_expected_slide_count(plan: dict[str, Any], composition: dict[str, Any]) -> int:
    pagination = composition.get("pagination", {}) if isinstance(composition, dict) else {}
    expanded = pagination.get("expandedSlideCount")
    if isinstance(expanded, int) and expanded > 0:
        return expanded
    return len(plan.get("slides", []))


def composition_visual_slides(composition: dict[str, Any]) -> list[int]:
    slides = composition.get("slides", []) if isinstance(composition, dict) else []
    result = []
    for slide in slides:
        if slide.get("role") == "content" and slide.get("addedImages"):
            output = slide.get("outputSlide")
            if isinstance(output, int):
                result.append(output)
    return result


def qa(project_dir: Path, pptx: Path, plan_path: Path, report_path: Path | None = None) -> dict[str, Any]:
    plan = read_json(plan_path)
    composition = read_json(report_path) if report_path and report_path.exists() else {}
    entries = load_entries(pptx)
    slide_w, slide_h = slide_size(entries)
    slides = slide_paths(entries)
    rel_issues = relationship_issues(entries)
    texts = []
    for slide_path in slides:
        root = parse_xml(entries[slide_path])
        texts.extend(slide_texts(root))
    ellipsis_hits = [text for text in texts if "..." in text or "…" in text]
    placeholder_hits = placeholder_prompt_hits(entries)
    overflows = added_shape_overflows(entries, slide_w, slide_h)
    malformed_xfrms = incomplete_xfrm_shapes(entries)
    layout_missing = slide_layout_relationships(entries)
    image_counts = count_slide_images(entries)
    visual_slide_numbers = composition_visual_slides(composition) or planned_visual_slides(plan)
    visual_slides_without_images = [slide_no for slide_no in visual_slide_numbers if image_counts.get(slide_no, 0) == 0]
    planned_visuals = planned_visual_count(plan)
    added_images = int(composition.get("addedImageCount", composition.get("visibleVisualAssetCount", 0)) or 0)
    expected_slide_count = composition_expected_slide_count(plan, composition)

    checks = {
        "pptxZipReadable": True,
        "slideCountMatchesPlan": len(slides) == expected_slide_count,
        "relationshipTargetsExist": len(rel_issues) == 0,
        "noVisibleEllipsis": len(ellipsis_hits) == 0,
        "noTemplatePlaceholderPrompts": len(placeholder_hits) == 0,
        "addedShapesWithinSlide": len(overflows) == 0,
        "shapeTransformsComplete": len(malformed_xfrms) == 0,
        "visualAssetCountSatisfied": added_images >= planned_visuals,
        "visualSlidesHaveImages": len(visual_slides_without_images) == 0,
        "templateSlideLayoutsPreserved": len(layout_missing) == 0,
    }
    result = {
        "version": 1,
        "stage": "step_6_pptx_qa",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "projectDir": str(project_dir),
        "pptx": str(pptx),
        "plan": str(plan_path),
        "compositionReport": str(report_path) if report_path else None,
        "summary": {
            "passed": all(checks.values()),
            "slideCount": len(slides),
            "plannedSlideCount": expected_slide_count,
            "plannedVisualAssetCount": planned_visuals,
            "addedImageCount": added_images,
            "ellipsisHitCount": len(ellipsis_hits),
            "templatePlaceholderPromptCount": len(placeholder_hits),
            "overflowCount": len(overflows),
            "incompleteShapeTransformCount": len(malformed_xfrms),
            "missingRelationshipTargetCount": len(rel_issues),
            "visualSlidesWithoutImagesCount": len(visual_slides_without_images),
            "slidesMissingLayoutRelationshipCount": len(layout_missing),
        },
        "checks": checks,
        "issues": {
            "relationshipTargets": rel_issues[:50],
            "ellipsisTexts": ellipsis_hits[:50],
            "templatePlaceholderPrompts": placeholder_hits[:50],
            "addedShapeOverflows": overflows[:50],
            "incompleteShapeTransforms": malformed_xfrms[:50],
            "visualSlidesWithoutImages": visual_slides_without_images,
            "slidesMissingLayoutRelationship": layout_missing,
        },
    }
    return result


def default_paths(project_dir: Path) -> tuple[Path, Path, Path, Path]:
    output_dir = project_dir / "output"
    plan = project_dir / "ppt-generation-plan.json"
    if not plan.exists():
        plan = project_dir / "slide-plan.json"
    pptx = output_dir / "fund-pension-annuity-step3b-draft.pptx"
    composition = output_dir / "composition-report.json"
    return (
        plan,
        pptx,
        composition,
        output_dir / "qa-report.json",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QA checks for generated PPTX.")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--composition-report", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    default_plan, default_pptx, default_composition, default_out = default_paths(args.project_dir)
    plan = args.plan or default_plan
    pptx = args.pptx or default_pptx
    composition = args.composition_report or default_composition
    out = args.out or default_out
    result = qa(args.project_dir.resolve(), pptx.resolve(), plan.resolve(), composition.resolve())
    write_json(out, result)
    print(json.dumps({"passed": result["summary"]["passed"], **result["summary"], "report": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


