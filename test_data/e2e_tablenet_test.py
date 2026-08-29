"""端到端冒烟：PDF -> tablenet 模型 -> HTML -> outputs。

用主后端环境运行（不 import torch），engine 会自动拉起 tablenet-venv 模型服务。
用法: python test_data/e2e_tablenet_test.py [pdf路径]
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from tablenet.engine import engine
from rag.pdf_table_recognition import recognize_pdf_tables

pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_table.pdf")
pdf = os.path.abspath(pdf)

print("status:", engine.status())
res = recognize_pdf_tables(pdf, filename=os.path.basename(pdf), engine=engine)
print("success:", res["success"], "| tables:", res["tables_count"])
print("run_dir:", res["run_dir"])
for t in res["tables"]:
    print(f"  page={t['page']} idx={t['index']} source={t['source']} error={t.get('error','')!r}")
    print("  html:", (t.get("html") or "")[:120].replace("\n", " "))
    print("  md:", (t.get("markdown") or "")[:120].replace("\n", " | "))
print("files:", json.dumps(res["files"], ensure_ascii=False))
