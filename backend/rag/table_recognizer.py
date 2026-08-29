"""Table Structure Recognition Module

Detects and recognizes table structures from various sources:
- Table boundary detection
- Row/column split recognition
- Merged cell recovery (rowspan/colspan)
- Header hierarchy understanding
- Cell text binding
- Serialization to multiple formats
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class Cell:
    text: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    confidence: float = 1.0


@dataclass
class TableStructure:
    id: str = ""
    rows: int = 0
    cols: int = 0
    cells: List[Cell] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    header_rows: int = 0
    data_rows_start: int = 0
    merged_cells: List[Dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert to Markdown table"""
        if not self.headers:
            return self._to_markdown_simple()

        lines = []
        lines.append("| " + " | ".join(self.headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")

        data_cells = [c for c in self.cells if not c.is_header]
        row_map = {}
        for c in data_cells:
            if c.row not in row_map:
                row_map[c.row] = {}
            row_map[c.row][c.col] = c.text

        for row_idx in sorted(row_map.keys()):
            row_data = []
            for col_idx in range(self.cols):
                row_data.append(row_map[row_idx].get(col_idx, ""))
            lines.append("| " + " | ".join(row_data) + " |")

        return "\n".join(lines)

    def _to_markdown_simple(self) -> str:
        lines = []
        row_map = {}
        for c in self.cells:
            if c.row not in row_map:
                row_map[c.row] = {}
            row_map[c.row][c.col] = c.text

        for row_idx in sorted(row_map.keys()):
            row_data = [row_map[row_idx].get(c, "") for c in range(self.cols)]
            if row_idx == 0:
                lines.append("| " + " | ".join(row_data) + " |")
                lines.append("| " + " | ".join(["---"] * self.cols) + " |")
            else:
                lines.append("| " + " | ".join(row_data) + " |")
        return "\n".join(lines)

    def to_csv(self) -> str:
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        if self.headers:
            writer.writerow(self.headers)
        row_map = {}
        for c in self.cells:
            if not c.is_header:
                if c.row not in row_map:
                    row_map[c.row] = {}
                row_map[c.row][c.col] = c.text
        for row_idx in sorted(row_map.keys()):
            writer.writerow([row_map[row_idx].get(c, "") for c in range(self.cols)])
        return output.getvalue().strip()

    def to_json(self) -> Dict:
        # Build 2D data_rows array from flat cell list
        data_rows = []
        row_map = {}
        for c in self.cells:
            if not c.is_header:
                if c.row not in row_map:
                    row_map[c.row] = {}
                row_map[c.row][c.col] = c.text
        for row_idx in sorted(row_map.keys()):
            row_data = [row_map[row_idx].get(c, "") for c in range(self.cols)]
            data_rows.append(row_data)

        return {
            "rows": self.rows,
            "cols": self.cols,
            "headers": self.headers,
            "header_rows": self.header_rows,
            "data": [
                {
                    "row": c.row,
                    "col": c.col,
                    "text": c.text,
                    "rowspan": c.rowspan,
                    "colspan": c.colspan,
                    "is_header": c.is_header
                }
                for c in self.cells
            ],
            "data_rows": data_rows,
            "merged_cells": self.merged_cells
        }


class TableRecognizer:
    """Table structure recognizer supporting multiple input sources"""

    @staticmethod
    def recognize_from_csv(csv_path: str, sheet_name: str = "Sheet1") -> TableStructure:
        """Recognize table structure from CSV"""
        import csv
        table = TableStructure(id=f"csv:{sheet_name}")

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return table

        table.rows = len(rows)
        table.cols = max(len(r) for r in rows)
        table.header_rows = 1
        table.headers = rows[0]
        table.data_rows_start = 1

        for row_idx, row in enumerate(rows):
            for col_idx, cell_text in enumerate(row):
                cell = Cell(
                    text=cell_text.strip(),
                    row=row_idx,
                    col=col_idx,
                    is_header=(row_idx == 0)
                )
                table.cells.append(cell)

        return table

    @staticmethod
    def recognize_from_text(text: str, table_id: str = "text_table") -> TableStructure:
        """Recognize table from text with tabular patterns"""
        table = TableStructure(id=table_id)
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        data_rows = []
        for line in lines:
            if '\t' in line:
                cells = line.split('\t')
            elif '|' in line:
                cells = [c.strip() for c in line.split('|') if c.strip()]
            else:
                cells = re.split(r'\s{2,}', line)
            if len(cells) >= 2:
                data_rows.append(cells)

        if not data_rows:
            return table

        table.cols = max(len(r) for r in data_rows)
        table.rows = len(data_rows)
        table.header_rows = 1
        table.headers = data_rows[0]
        table.data_rows_start = 1

        for row_idx, row in enumerate(data_rows):
            for col_idx, cell_text in enumerate(row):
                cell = Cell(
                    text=cell_text.strip(),
                    row=row_idx,
                    col=col_idx,
                    is_header=(row_idx == 0)
                )
                table.cells.append(cell)

        return table

    @staticmethod
    def recognize_from_markdown(md_table: str, table_id: str = "md_table") -> TableStructure:
        """Recognize table from Markdown format"""
        table = TableStructure(id=table_id)
        lines = md_table.strip().split('\n')

        # Remove separator line
        data_lines = [lines[0]] + lines[2:] if len(lines) > 2 and '---' in lines[1] else lines

        data_rows = []
        for line in data_lines:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                data_rows.append(cells)

        if not data_rows:
            return table

        table.cols = max(len(r) for r in data_rows)
        table.rows = len(data_rows)
        table.header_rows = 1
        table.headers = data_rows[0]
        table.data_rows_start = 1

        for row_idx, row in enumerate(data_rows):
            for col_idx, cell_text in enumerate(row):
                cell = Cell(
                    text=cell_text.strip(),
                    row=row_idx,
                    col=col_idx,
                    is_header=(row_idx == 0)
                )
                table.cells.append(cell)

        return table

    @staticmethod
    def recognize_from_html(html_table: str, table_id: str = "html_table") -> TableStructure:
        """Recognize table from HTML"""
        table = TableStructure(id=table_id)
        # Extract <table> content
        soup_match = re.search(r'<table[^>]*>(.*?)</table>', html_table, re.DOTALL)
        if not soup_match:
            return table
        table_html = soup_match.group(1)

        # Extract rows
        row_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)

        data_rows = []
        for row_idx, row_html in enumerate(row_matches):
            cells = []
            # th and td
            for cell_match in re.finditer(r'<(th|td)[^>]*>(.*?)</\1>', row_html, re.DOTALL):
                tag, content = cell_match.group(1), cell_match.group(2).strip()
                # Clean HTML tags
                content = re.sub(r'<[^>]+>', '', content)
                colspan = int(re.search(r'colspan\s*=\s*["\']?(\d+)', cell_match.group(0)).group(1)) \
                    if re.search(r'colspan\s*=\s*["\']?(\d+)', cell_match.group(0)) else 1
                rowspan = int(re.search(r'rowspan\s*=\s*["\']?(\d+)', cell_match.group(0)).group(1)) \
                    if re.search(r'rowspan\s*=\s*["\']?(\d+)', cell_match.group(0)) else 1
                cells.append({
                    'text': content,
                    'colspan': colspan,
                    'rowspan': rowspan,
                    'is_header': tag == 'th'
                })
            if cells:
                data_rows.append(cells)

        if not data_rows:
            return table

        # Detect merged cells
        table.cols = sum(c['colspan'] for c in data_rows[0])
        table.rows = len(data_rows)
        table.header_rows = 1 if any(c['is_header'] for c in data_rows[0]) else 0
        table.headers = [c['text'] for c in data_rows[0]]

        used_cells = set()
        for row_idx, row in enumerate(data_rows):
            col_idx = 0
            for cell_info in row:
                while (row_idx, col_idx) in used_cells:
                    col_idx += 1
                cell = Cell(
                    text=cell_info['text'],
                    row=row_idx,
                    col=col_idx,
                    rowspan=cell_info['rowspan'],
                    colspan=cell_info['colspan'],
                    is_header=cell_info['is_header']
                )
                table.cells.append(cell)

                # Mark merged cell positions
                for i in range(cell_info['rowspan']):
                    for j in range(cell_info['colspan']):
                        used_cells.add((row_idx + i, col_idx + j))

                if cell_info['colspan'] > 1 or cell_info['rowspan'] > 1:
                    table.merged_cells.append({
                        "row": row_idx,
                        "col": col_idx,
                        "rowspan": cell_info['rowspan'],
                        "colspan": cell_info['colspan'],
                        "text": cell_info['text']
                    })

                col_idx += cell_info['colspan']

        table.data_rows_start = table.header_rows
        return table

    @staticmethod
    def recognize_from_image(image_path: str, table_id: str = "img_table") -> TableStructure:
        """Attempt table recognition from image using OCR structure analysis"""
        table = TableStructure(id=table_id)
        try:
            from PIL import Image
            import pytesseract

            img = Image.open(image_path)

            # Get detailed OCR data with bounding boxes
            ocr_data = pytesseract.image_to_data(
                img, lang='chi_sim+eng',
                output_type=pytesseract.Output.DICT
            )

            # Group text by lines, then detect columns
            lines_data = {}
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                if not text:
                    continue
                line_num = ocr_data['line_num'][i]
                if line_num not in lines_data:
                    lines_data[line_num] = []
                lines_data[line_num].append({
                    'text': text,
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'conf': ocr_data['conf'][i]
                })

            # Cluster into columns based on x-coordinates
            sorted_lines = sorted(lines_data.items(), key=lambda x: x[0])
            if not sorted_lines:
                return table

            # Detect column boundaries from first row
            first_row_words = sorted_lines[0][1]
            if len(first_row_words) < 2:
                # Not a table
                return table

            # Build structure
            table.rows = len(sorted_lines)
            table.cols = len(first_row_words)
            table.headers = [w['text'] for w in first_row_words]
            table.header_rows = 1

            for line_num, words in sorted_lines:
                for i, word in enumerate(words):
                    if i < len(first_row_words):
                        cell = Cell(
                            text=word['text'],
                            row=line_num - 1,
                            col=i,
                            is_header=(line_num == list(lines_data.keys())[0]),
                            confidence=word['conf'] / 100.0
                        )
                        table.cells.append(cell)

        except ImportError as e:
            table = TableStructure(id=table_id)
            table.rows = 0

        return table

    @staticmethod
    def detect_separator_line(md_separator: str) -> bool:
        """Check if a line is a markdown table separator"""
        return bool(re.match(r'^[\s\|:-]+$', md_separator)) and '---' in md_separator


def analyze_table_complexity(table: TableStructure) -> Dict:
    """Analyze table complexity for evaluating recognition difficulty"""
    merged_count = len(table.merged_cells)
    has_multi_headers = table.header_rows > 1
    empty_cells = sum(1 for c in table.cells if not c.text.strip())

    return {
        "rows": table.rows,
        "cols": table.cols,
        "total_cells": len(table.cells),
        "merged_cells_count": merged_count,
        "has_multi_level_headers": has_multi_headers,
        "empty_cells": empty_cells,
        "empty_cell_ratio": round(empty_cells / max(len(table.cells), 1), 3),
        "is_complex": merged_count > 0 or has_multi_headers
    }
