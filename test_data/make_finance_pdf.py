"""生成一个含财务表格的测试 PDF，用于验证"文档管理×表格识别×金融问答"。"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance_sample.pdf")

rows = [
    ["项目", "2020年", "2021年", "2022年"],
    ["营业收入(亿元)", "512.3", "661.8", "885.7"],
    ["营业成本(亿元)", "342.1", "430.5", "624.5"],
    ["毛利润(亿元)", "170.2", "231.3", "261.2"],
    ["净利润(亿元)", "36.2", "48.7", "72.9"],
    ["总资产(亿元)", "812.4", "968.3", "1245.6"],
]

fig, ax = plt.subplots(figsize=(8, 4))
ax.axis("off")
table = ax.table(
    cellText=rows,
    cellLoc="center",
    colWidths=[0.22, 0.18, 0.18, 0.18],
    loc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.5)
for (r, c), cell in table.get_celld().items():
    if r == 0:
        cell.set_facecolor("#d9e2f3")
        cell.set_text_props(fontweight="bold")

fig.savefig(OUT)
print("saved", OUT)
