---
deck_id: guotai_fund_standard
kind: deck
category: brand
summary: 国泰基金品牌化金融汇报模板，适用于基金公司汇报、投资产品介绍、策略复盘与数据报告。
keywords: [国泰基金, 金融报告, 企业汇报, 红灰金, 数据可视化]
primary_color: "#9E0116"
canvas_format: ppt169
replication_mode: fidelity
page_count: 20
---

# 国泰基金标准页面库 — Design Specification

## I. Template Overview

- **Use cases**：基金公司内部汇报、投资与产品介绍、经营分析、策略复盘、季度及年度数据报告。
- **Design tone**：专业、克制、可信、数据导向。
- **Theme mode**：浅色，以大面积白色留白承载信息，以国泰红建立层级，以灰色和金色区分辅助内容。
- **Visual identity**：横向红色短线、浅灰标题带、国泰基金 Logo、红/深红/灰/金的轮换强调，以及封面和结束页的城市天际线。

## II. Color Scheme

| Role | HEX | Application |
|---|---|---|
| Guotai Red | `#9E0116` | 标题、编号、关键节点、主强调 |
| Deep Red | `#5D070C` | 次级节点、深色数据强调 |
| Graphite | `#262626` | 正文与主标签 |
| Mid Gray | `#706F71` | 次要信息、第三序列 |
| Light Gray | `#A7A7A7` | 弱化节点、辅助对比 |
| Warm Gold | `#BF9D5A` | 金融属性强调、第五序列 |
| Pale Gold | `#D8C49B` | 金色浅背景与细线 |
| Panel Gray | `#F2F2F2` | 内容带、卡片底、结构区 |
| Background | `#FFFFFF` | 页面主背景 |

## III. Signature Design Elements

- 页面顶部使用 400px 左右的国泰红短线，随后接浅灰标题带，形成稳定的内容页识别。
- 内容页底部保留小型品牌 Logo 与细红页码，品牌存在感克制但连续。
- 多项信息按国泰红 → 深红 → 中灰 → 浅灰 → 金色轮换，保持金融报告中的次序与权重感。
- 封面、章节和结束页使用城市天际线、国泰中心建筑和金色地平线作为固定视觉锚点。
- 图表、流程和环形关系优先使用平面几何、细线与空心节点，不使用厚重阴影。

## IV. Page Roster

| File | Role | Fidelity cluster and intended content |
|---|---|---|
| `01_cover.svg` | cover | 源第 1 页；城市天际线封面，适合公司级报告标题、组织、日期。 |
| `02_toc.svg` | toc | 源第 2 页；五项编号目录，适合正式汇报的主章节导航。 |
| `02a_toc_compact.svg` | toc | 源第 42 页；左侧色块加右侧紧凑列表，适合长目录或附录导航。 |
| `02_chapter.svg` | chapter | 源第 3 页；大号章节编号、标题与城市底景，适合强分节。 |
| `02a_chapter_overview.svg` | chapter | 源第 4 页；章节编号、标题和三条概述，适合进入章节前先交代范围。 |
| `03_content.svg` | content | 源第 5/44 页；开放内容画布，适合单一核心观点、图表或自由组合。 |
| `03a_content_three_columns.svg` | content | 源第 5/20/51 页；三栏并列卡片，适合能力、方案或结论对比。 |
| `03b_content_four_metrics.svg` | content | 源第 7/17/48 页；四项指标或四卡片并列，适合数据摘要和支柱框架。 |
| `03c_content_process.svg` | content | 源第 6/18/27/34 页；横向阶段流程，适合实施路径、演进路线、工作步骤。 |
| `03d_content_radial.svg` | content | 源第 9/15/16/35 页；中心主题加四向环形信息，适合核心能力或驱动因素。 |
| `03e_content_table.svg` | content | 源第 12/26/40 页；红色表头与分组表格，适合方案比较、计划和矩阵信息。 |
| `03f_content_comparison.svg` | content | 源第 20/33/38 页；左右或四象限对比，适合对象、方案与阶段差异。 |
| `03g_content_media_split.svg` | content | 源第 8/44/50 页；图像区与文本区分屏，适合案例、产品与重点说明。 |
| `03h_content_timeline.svg` | content | 源第 21/23/37/46 页；纵向/折线时间轴，适合年度演进和里程碑。 |
| `03i_content_grid.svg` | content | 源第 10/11/13/29/43 页；模块网格，适合多能力、多部门或多任务陈列。 |
| `03j_content_chart_notes.svg` | content | 源第 25/30/31 页；主图表加解释区，适合数据图、案例图和结论说明。 |
| `03k_content_cycle.svg` | content | 源第 24/36/39 页；环形或连续节点关系，适合闭环机制与协同关系。 |
| `03l_content_partner.svg` | content | 源第 28 页；双 Logo 合作页，适合联合方案、合作框架和签约信息。 |
| `03m_content_five_steps.svg` | content | 源第 36/49 页；五阶段横向链路，适合完整流程或五项原则。 |
| `04_ending.svg` | ending | 源第 52 页；感谢语、城市线稿与网络光效，适合正式收束。 |

## V. Assets

| File | Dimensions | Intended usage |
|---|---:|---|
| `brand_logo_header.png` | 252 × 70 | 封面、目录、章节和结束页品牌标识 |
| `brand_logo_footer.png` | 150 × 42 | 内容页页脚品牌标识 |
| `skyline_cover.png` | 2001 × 705 | 封面与章节底部城市天际线 |
| `network_glow.png` | 2000 × 707 | 结束页城市网络光效 |
| `skyline_closing.png` | 2000 × 1520 | 结束页城市线稿 |
