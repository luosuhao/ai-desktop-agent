"""PDF 表格识别流水线（Qwen2-VL-TableNet）。

流程：PyMuPDF 渲染页面 -> pdfplumber 检测表格区域 -> 裁剪表格图片 ->
调用 tablenet 模型转 HTML -> 汇总输出到 outputs/tablenet/<run_id>/。
"""

import os
import re
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from rag.table_recognizer import TableRecognizer


DPI = 150
SCALE = DPI / 72.0  # PDF 点 -> 像素
MARGIN_PT = 8.0     # 裁剪时四周留白（点）


def _render_pages(pdf_path: str, out_dir: str) -> List[dict]:
    """用 PyMuPDF 把每一页渲染为 PNG，返回页面尺寸信息。"""
    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
        img_path = os.path.join(out_dir, f"page_{i}.png")
        pix.save(img_path)
        pages.append({
            "index": i,
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "width_px": pix.width,
            "height_px": pix.height,
            "image_path": img_path,
        })
    doc.close()
    return pages


def _detect_table_bboxes(pdf_path: str, page_index: int) -> List[Tuple[float, float, float, float]]:
    """用 pdfplumber 检测某一页的表格边界框（PDF 点坐标）。

    依次尝试基于网格线（lines）与基于文字对齐（text）两种策略。
    """
    import pdfplumber
    bboxes = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index - 1]
        for strategy in ("lines", "text"):
            try:
                settings = {"vertical_strategy": strategy, "horizontal_strategy": strategy}
                for table in page.find_tables(settings):
                    bboxes.append(tuple(table.bbox))
            except Exception:
                continue
    return _dedupe_bboxes(bboxes)


def _dedupe_bboxes(bboxes: List[Tuple[float, float, float, float]],
                   iou_threshold: float = 0.5) -> List[Tuple[float, float, float, float]]:
    """去掉重叠度高的重复 bbox（lines 与 text 策略可能重复检出）。"""
    kept = []
    for b in bboxes:
        duplicate = False
        for k in kept:
            ix = max(0, min(b[2], k[2]) - max(b[0], k[0]))
            iy = max(0, min(b[3], k[3]) - max(b[1], k[1]))
            inter = ix * iy
            area = (b[2] - b[0]) * (b[3] - b[1]) + 1e-6
            if inter / area > iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(b)
    return kept


def _crop_table_image(page_info: dict, bbox: Tuple[float, float, float, float],
                      out_path: str) -> bool:
    """从页面 PNG 裁剪表格区域（带留白），返回是否成功。"""
    from PIL import Image
    try:
        img = Image.open(page_info["image_path"])
        left = max(0, int((bbox[0] - MARGIN_PT) * SCALE))
        top = max(0, int((bbox[1] - MARGIN_PT) * SCALE))
        right = min(img.width, int((bbox[2] + MARGIN_PT) * SCALE))
        bottom = min(img.height, int((bbox[3] + MARGIN_PT) * SCALE))
        if right - left < 10 or bottom - top < 10:
            return False
        crop = img.crop((left, top, right, bottom))
        crop.save(out_path)
        return True
    except Exception:
        return False


def _table_to_markdown(html: str) -> str:
    """把模型输出的表格 HTML 转成 Markdown（复用 TableRecognizer）。"""
    table = TableRecognizer.recognize_from_html(html)
    if table.cells:
        # 模型输出全为 <td>，无 <th>：把第一行显式标记为表头，
        # 避免 TableRecognizer 把表头行同时当作数据行导致表头重复。
        if table.header_rows == 0:
            for c in table.cells:
                if c.row == 0:
                    c.is_header = True
            table.header_rows = 1
        return table.to_markdown()
    # 解析失败时退化为原始文本
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def merge_tablenet_tables(parsed, recognition: dict) -> int:
    """把 TableNet 识别结果并入 ParsedDocument.tables，返回合并的表数。

    每个表格还原出 headers/data 结构化数据并存 markdown/html/run_id。
    成功合并时移除启发式 pdf_text 表格，避免同一张表被两套解析器双份索引。
    """
    tables = recognition.get("tables", []) or []
    if not tables:
        return 0

    merged = []
    for idx, t in enumerate(tables):
        md = (t.get("markdown") or "").strip()
        if not md:
            continue
        try:
            structure = TableRecognizer.recognize_from_markdown(
                md, f"{parsed.id}_tl{idx + 1}")
            headers = structure.headers or []
            data_rows = structure.to_json().get("data_rows", []) or []
        except Exception:
            headers, data_rows = [], []
        merged.append({
            "page_num": t.get("page", 1),
            "index": t.get("index", idx + 1),
            "source": "tablenet",
            "run_id": recognition.get("run_id", ""),
            "image_path": t.get("image_path", ""),
            "html": t.get("html", ""),
            "rows": len(data_rows),
            "cols": len(headers) or (max((len(r) for r in data_rows), default=0)),
            "headers": headers,
            "data": data_rows,
            "markdown": md,
            "error": t.get("error", ""),
        })

    if merged:
        parsed.tables = [tb for tb in parsed.tables
                         if tb.get("source") != "pdf_text"]
        parsed.tables.extend(merged)
    return len(merged)


def recognize_pdf_tables(
    pdf_path: str,
    filename: str = "",
    engine=None,
    output_root: str = None,
    max_new_tokens: int = 2048,
    page_fallback: bool = False,
) -> Dict:
    """识别 PDF 中的表格，全部输出到 output_root/tablenet/<run_id>/。

    engine 需提供 predict(image_path, max_new_tokens) -> {"html": ...}。
    返回包含每个表格的 HTML / Markdown / 文件路径的字典。
    """
    from config import settings

    stem = os.path.splitext(os.path.basename(filename or pdf_path))[0]
    run_id = f"{stem}_{datetime.now().strftime('%H%M%S')}"
    run_dir = os.path.join(output_root or settings.output_dir, "tablenet", run_id)
    os.makedirs(run_dir, exist_ok=True)

    # 1) 复制原 PDF
    pdf_copy = os.path.join(run_dir, "input.pdf")
    shutil.copyfile(pdf_path, pdf_copy)

    # 2) 渲染页面
    pages = _render_pages(pdf_path, run_dir)

    # 3) 逐页检测 + 裁剪表格
    table_results: List[Dict] = []
    for page in pages:
        bboxes = _detect_table_bboxes(pdf_path, page["index"])
        if not bboxes and page_fallback:
            # 回退：整页作为一张表处理
            crop_path = os.path.join(run_dir, f"table_{page['index']}_1.png")
            shutil.copyfile(page["image_path"], crop_path)
            table_results.append({
                "page": page["index"],
                "index": 1,
                "source": "page",
                "image_path": crop_path,
                "html": "",
                "markdown": "",
            })
            continue
        for idx, bbox in enumerate(bboxes, 1):
            crop_path = os.path.join(run_dir, f"table_{page['index']}_{idx}.png")
            if not _crop_table_image(page, bbox, crop_path):
                continue
            table_results.append({
                "page": page["index"],
                "index": idx,
                "source": "table",
                "bbox": list(bbox),
                "image_path": crop_path,
                "html": "",
                "markdown": "",
            })

    # 4) 逐表推理
    for t in table_results:
        if engine is None:
            continue
        resp = engine.predict(t["image_path"], max_new_tokens=max_new_tokens)
        html = resp.get("html", "")
        t["html"] = html
        t["error"] = resp.get("error", "")
        t["markdown"] = _table_to_markdown(html) if html else ""
        # 保存单表 HTML
        html_path = os.path.join(
            run_dir, f"table_{t['page']}_{t['index']}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    # 5) 汇总输出
    _write_summaries(run_dir, table_results)

    result = {
        "success": True,
        "run_id": run_id,
        "run_dir": run_dir,
        "tables_count": len(table_results),
        "tables": table_results,
        "files": {
            "pdf": os.path.abspath(pdf_copy),
            "index_json": os.path.abspath(os.path.join(run_dir, "index.json")),
            "result_md": os.path.abspath(os.path.join(run_dir, "result.md")),
            "result_html": os.path.abspath(os.path.join(run_dir, "result.html")),
        },
    }
    # 元数据写 index.json
    try:
        with open(os.path.join(run_dir, "index.json"), "w", encoding="utf-8") as f:
            json.dump({
                "source": filename,
                "run_id": run_id,
                "model": "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                "params": {"image_size": 280, "max_new_tokens": max_new_tokens,
                           "do_sample": False, "adapter": "", "ocr": "none"},
                "tables": [
                    {k: (v if k != "html" else None) for k, v in t.items()}
                    for t in table_results
                ],
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


def _write_summaries(run_dir: str, table_results: List[Dict]):
    """生成 result.md 与 result.html 汇总文件。"""
    md_lines = [f"# PDF 表格识别结果（{len(table_results)} 张表）", ""]
    html_parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
                  "<title>PDF 表格识别结果</title>",
                  "<style>table{border-collapse:collapse;margin:12px 0}"
                  "th,td{border:1px solid #999;padding:4px 8px}</style>",
                  "</head><body>",
                  f"<h2>PDF 表格识别结果（{len(table_results)} 张表）</h2>"]
    for i, t in enumerate(table_results, 1):
        title = f"## 表格 {i}（第 {t['page']} 页，来源 {t['source']}）"
        md_lines.append(title)
        md_lines.append("")
        md_lines.append(t["markdown"] or "(识别失败)")
        md_lines.append("")
        html_parts.append(f"<h3>表格 {i}（第 {t['page']} 页）</h3>")
        if t.get("html"):
            html_parts.append(t["html"])
        else:
            html_parts.append("<p>(识别失败)</p>")
    html_parts.append("</body></html>")

    with open(os.path.join(run_dir, "result.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    with open(os.path.join(run_dir, "result.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


def recognize_image_tables(
    image_path: str,
    filename: str = "",
    engine=None,
    output_root: str = None,
    max_new_tokens: int = 2048,
) -> Dict:
    """识别图片/图表中的表格（Qwen2-VL-TableNet 直通推理）。

    不走 PDF 渲染/表格检测流水线，把原图直接喂给模型。
    输出结构与 recognize_pdf_tables 保持一致，前端可复用同一套展示逻辑。
    """
    from config import settings

    stem = os.path.splitext(os.path.basename(filename or image_path))[0]
    run_id = f"{stem}_{datetime.now().strftime('%H%M%S')}"
    run_dir = os.path.join(output_root or settings.output_dir, "tablenet", run_id)
    os.makedirs(run_dir, exist_ok=True)

    # 复制原图为 table_1_1.png（前端下载链接 table_{page}_{index}.png 依赖此命名）
    img_copy = os.path.join(run_dir, "table_1_1.png")
    shutil.copyfile(image_path, img_copy)

    table = {
        "page": 1,
        "index": 1,
        "source": "image",
        "image_path": img_copy,
        "html": "",
        "markdown": "",
    }
    if engine is not None:
        resp = engine.predict(img_copy, max_new_tokens=max_new_tokens)
        html = resp.get("html", "")
        table["html"] = html
        table["error"] = resp.get("error", "")
        table["markdown"] = _table_to_markdown(html) if html else ""
        html_path = os.path.join(run_dir, "table_1_1.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    table_results = [table]
    _write_summaries(run_dir, table_results)

    result = {
        "success": True,
        "run_id": run_id,
        "run_dir": run_dir,
        "tables_count": len(table_results),
        "tables": table_results,
        "files": {
            "pdf": os.path.abspath(img_copy),
            "index_json": os.path.abspath(os.path.join(run_dir, "index.json")),
            "result_md": os.path.abspath(os.path.join(run_dir, "result.md")),
            "result_html": os.path.abspath(os.path.join(run_dir, "result.html")),
        },
    }
    try:
        with open(os.path.join(run_dir, "index.json"), "w", encoding="utf-8") as f:
            json.dump({
                "source": filename,
                "run_id": run_id,
                "model": "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                "params": {"image_size": 280, "max_new_tokens": max_new_tokens,
                           "do_sample": False, "adapter": "", "ocr": "none"},
                "tables": [
                    {k: (v if k != "html" else None) for k, v in t.items()}
                    for t in table_results
                ],
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result
