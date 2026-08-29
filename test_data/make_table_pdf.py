"""生成一个带表格的测试 PDF，用于 Qwen2-VL-TableNet 冒烟测试。

用 matplotlib 渲染表格并保存为 PDF（含网格线，便于 pdfplumber 检测）。
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

rows = [
    ["姓名", "部门", "工龄(年)", "月薪(元)"],
    ["张三", "研发部", "5", "15000"],
    ["李四", "测试部", "3", "12000"],
    ["王五", "产品部", "8", "18000"],
    ["赵六", "运维部", "2", "10000"],
    ["孙七", "市场部", "6", "16000"],
]

fig, ax = plt.subplots(figsize=(6, 4))
ax.axis("off")
table = ax.table(
    cellText=rows,
    cellLoc="center",
    colWidths=[0.18, 0.22, 0.25, 0.25],
    loc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.2, 1.5)
for (r, c), cell in table.get_celld().items():
    if r == 0:
        cell.set_facecolor("#d9e2f3")
        cell.set_text_props(fontweight="bold")

fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_table.pdf"))
print("saved sample_table.pdf")
