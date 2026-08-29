"""稳健的 Python 代码提取工具（容忍未闭合的 markdown 围栏）。"""
import re


def extract_python_code(text):
    """从 LLM 输出中提取 Python 代码。"""
    if not text:
        return ""
    t = text.strip()
    # 1) 标准围栏块（含闭合 ```）
    m = re.search(r"```(?:python|py)?\s*\n?([\s\S]*?)```", t)
    if m:
        return m.group(1).strip()
    # 2) 围栏被截断（只有开头的 ```，无闭合）：去掉首行围栏标记
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        t = "\n".join(lines).strip()
    if t.endswith("```"):
        t = t[:-3].rstrip()
    # 去掉首尾可能的语言标记行
    if t.startswith("python"):
        t = t[len("python"):].lstrip()
    return t
