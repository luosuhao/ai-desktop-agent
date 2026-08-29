"""Markdown Report Generation Skill

Generates Markdown reports/papers from structured sections, tables, and figures.
No external compilation needed (unlike LaTeX). Output is a .md file.
"""

import os
import re
from typing import Dict, List
from datetime import datetime
from .skill_manager import Skill


class MarkdownReportSkill(Skill):
    """Skill for generating Markdown documents"""

    def __init__(self):
        super().__init__()
        self.name = "markdown-report-skill"
        self.description = "Generate Markdown papers and reports"
        self.trigger = "生成报告 生成论文 Markdown 论文 建模论文 报告"
        self.input_schema = {
            "type": "object",
            "required": ["title", "sections"],
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "author": {"type": "string", "description": "Author name"},
                "date": {"type": "string", "description": "Date"},
                "sections": {
                    "type": "array",
                    "description": "List of sections with title and content"
                },
                "tables": {"type": "array", "description": "Tables as markdown/CSV strings"},
                "figures": {"type": "array", "description": "Figure paths with captions"},
                "references": {"type": "array", "description": "Bibliography entries"}
            }
        }
        self.workflow = [
            "1. Parse input: title, author, sections, tables, figures",
            "2. Build document header with title/author/date",
            "3. Generate sections with markdown headings (#/##/###)",
            "4. Insert markdown tables",
            "5. Insert images with captions",
            "6. Add references section",
            "7. Save as .md file"
        ]
        self.tools = ["file_write"]
        self.validation = [
            "Markdown document generated without errors",
            "All headings use proper markdown syntax",
            "Tables are valid markdown format",
            "Images referenced correctly"
        ]
        self.examples = [
            {
                "input": {"title": "项目分析报告",
                          "sections": [{"title": "概述", "content": "..."}]},
                "output": "项目分析报告.md"
            }
        ]
        # ---- NVIDIA SKILL.md metadata ----
        self.constraints = [
            "禁止在内容中插入未转义的 HTML/脚本",
            "图片必须是可访问的本地路径",
            "不支持嵌入二进制附件"
        ]
        self.references = [
            "Markdown 指南: https://www.markdownguide.org",
            "GFM 规范: https://github.github.com/gfm"
        ]
        self.limitations = [
            "不包含高级排版（如页眉页脚、分页）",
            "复杂公式建议使用 LaTeX 数学表达式语法",
            "生成结果需在支持 Markdown 的编辑器中预览"
        ]
        self.owner = "AI Desktop System"
        self.lifecycle = "stable"
        self.risk_level = "low"
        self.permissions = {"file_write": True, "command_exec": False, "network": False}
        self.dependencies = []
        # First-party official skill: self-sign so it verifies as trusted
        self.expected_hash = self.compute_hash()

    # Built-in writing instructions (lightweight technical-note GFM standard)
    WRITING_GUIDE = (
        "你将使用标准GFM Markdown撰写报告。\n"
        "1. 标题层级最多4级，合理划分章节；支持行内/块公式、带标记代码块、Markdown表格；\n"
        "2. 行文简洁，侧重技术逻辑与数据展示；\n"
        "3. 无需生成正式图编号、表编号，不需要严格GB/T7714参考文献格式；\n"
        "4. 输出内容仅Markdown文本，不输出额外无关说明。"
    )

    def execute(self, inputs: Dict, output_dir: str = "./outputs") -> Dict:
        """Execute Markdown report generation (lightweight GFM technical note)"""
        title = inputs.get("title", "Untitled")
        author = inputs.get("author", "Author")
        date = inputs.get("date", datetime.now().strftime("%Y-%m-%d"))
        sections = inputs.get("sections", [])
        tables = inputs.get("tables", [])
        figures = inputs.get("figures", [])
        references = inputs.get("references", [])

        # Flexible default structure for technical notes
        if len(sections) < 3:
            defaults = [
                ("概述", "背景、目标、待解决问题"),
                ("方案/原理", "模型、算法、理论思路"),
                ("总结", "结论与后续计划"),
            ]
            existing = {sec.get("title", "") for sec in sections}
            for dtitle, dcontent in defaults:
                if dtitle not in existing:
                    sections.append({"title": dtitle, "content": dcontent, "level": "section"})

        os.makedirs(output_dir, exist_ok=True)

        # Build document parts
        parts = []

        # Header (title only, keep it lightweight)
        parts.append(f"# {title}\n")

        # Sections (GFM headings, max 4 levels)
        for sec in sections:
            sec_title = sec.get("title", "")
            sec_content = sec.get("content", "")
            level = sec.get("level", "section")

            heading = self._markdown_heading(sec_title, level)
            parts.append(f"{heading}\n{sec_content}\n")

        # Tables (plain GFM, no formal numbering)
        for i, table in enumerate(tables):
            table_content = table.get("content", "") if isinstance(table, dict) else str(table)
            parts.append(self._format_table(table_content))
            parts.append("")

        # Figures (inline image, no formal numbering)
        for fig in figures:
            fig_path = fig.get("path", "") if isinstance(fig, dict) else str(fig)
            caption = fig.get("caption", "") if isinstance(fig, dict) else ""
            parts.append(f"![{caption}]({fig_path})\n")

        # References (simple, not strict GB/T 7714)
        if references:
            parts.append("\n## 参考文献\n")
            for j, ref in enumerate(references, 1):
                parts.append(f"- {ref}")

        doc_content = "\n".join(parts)

        # Save markdown file
        md_filename = re.sub(r'[^\w\-_]', '_', title)[:50] + ".md"
        md_path = os.path.join(output_dir, md_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(doc_content)

        return {
            "md_file": md_path,
            "sections_count": len(sections),
            "tables_count": len(tables),
            "figures_count": len(figures),
            "writing_guide": self.WRITING_GUIDE,
            "validation": {
                "md_generated": True,
                "sections_included": len(sections) > 0
            }
        }

    def _markdown_heading(self, title: str, level: str) -> str:
        """Convert a section level to markdown heading"""
        mapping = {
            "section": "##",
            "subsection": "###",
            "subsubsection": "####"
        }
        prefix = mapping.get(level, "##")
        return f"{prefix} {title}"

    def _format_table(self, table_content: str) -> str:
        """Format a table string into valid markdown table.
        Accepts CSV-like or already-markdown table."""
        lines = [l.strip() for l in table_content.strip().split('\n') if l.strip()]
        if not lines:
            return "(空表格)"

        # If already markdown table (has |), return as-is
        if '|' in lines[0]:
            return table_content

        # Treat as CSV / tab-separated, convert to markdown table
        header = lines[0]
        if ',' in header:
            cells = [c.strip() for c in header.split(',')]
        elif '\t' in header:
            cells = [c.strip() for c in header.split('\t')]
        else:
            return table_content

        md_lines = ["| " + " | ".join(cells) + " |",
                    "|" + "---|" * len(cells)]
        for line in lines[1:]:
            if ',' in line:
                row_cells = [c.strip() for c in line.split(',')]
            elif '\t' in line:
                row_cells = [c.strip() for c in line.split('\t')]
            else:
                continue
            md_lines.append("| " + " | ".join(row_cells) + " |")

        return "\n".join(md_lines)
