---
name: ppt-template-generator
description: 从 Excel 工作簿生成用于原生 PowerPoint 模板填充的 PPT 内容规划产物。当 Codex 需要把包含文本备注、小型表格、长数据表和浮动图片的混合 Excel 来源解析为可编辑的 excel-content-manifest.json，渲染 PPT 风格的表格/图表视觉资产，并在保留已解析模板注册表的前提下为原生 PPT 组合创建 slide-plan.json 时使用。
---

# PPT 模板生成器

## 目的

按阶段构建生成侧流水线。第 1 步把 `.xlsx` 工作簿转换为可编辑的 `excel-content-manifest.json` 和提取出的原始资产。第 1 步不渲染表格或图表。第 2 步对每个表格资产分类，把简单表格渲染为带样式的表格 PNG，把较长的数值数据渲染为图表，并创建可编辑的 `slide-plan.json`。在第 3 步之前不要生成最终 PPTX。

## Excel 第 1 步工作流

运行：

```bash
python path/to/ppt-template-generator/scripts/excel_intake.py input.xlsx --output-dir project/intake
```

脚本写入：

```text
project/intake/
  excel-content-manifest.json
  picture-assets/
    <exported floating images>
  tables/
    <exported cell-block CSV files>
  table-assets/
    <exported table asset XLSX files>
```

使用 `references/content-manifest.schema.json` 作为 manifest 契约。

## Intake 规则

把 Excel 当作混合内容来源处理：

- `cellBlocks`：由空行和空列切分出的矩形工作表内容岛。孤立单元格或小型文本岛仍然保留。
- 在块检测期间，把合并单元格覆盖范围、视觉上较宽的文本、浮动图片锚定范围都视为占用单元格。Excel 常把长标签只存放在最左侧单元格里，但视觉上横跨多个空单元格；粘贴的图表/图片也会在视觉上覆盖单元格范围，却不是单元格值。仅在分段时计入这些相邻或被覆盖的单元格。如果表格和图片在视觉上相连，允许它们合并成一个更大的块，因为它们很可能是同一个语义资产。不要在导出的 CSV/XLSX 数据中伪造值。
- `textNotes`：内容工作表中的解释性文本，例如评论、洞察、图注、单位和备注。3 行或更少的块默认视为文本。
- `metricAssets`：标签/数值或 KPI 风格的单元格块。
- `tableAssets`：连续表格区域；每个表格既导出为 CSV 元数据来源，也导出为 `table-assets/` 下的独立 `.xlsx`。
- `imageAssets`：工作表中的浮动图片；把原始图片导出到 `picture-assets/`，并保留它们的工作表/范围锚点。有可用的邻近标题/上下文文本时，将其附加到图片。
- 以 `图：` 或 `图:` 开头的图注样式行，会作为源块上的 `captionRows` / `captionText` 记录。如果这类图注行在视觉上邻近某张图片，也复制到该图片的 `nearbyText` / `nearbyTextBlocks`，以便生成阶段把它用作图片描述。
- `structuredContent`：按工作表组织的人类可读大纲，包含 `title`、编号的 `textContent`、`tables` 和 `pictures`。
- `contentGroups`：按工作表把文本、表格和图片分组，使后续规划能够创建一页或多页 PPT 内容页。

不要丢弃浮动图片。许多工作簿图表是粘贴图片，而不是原生 Excel 图表。

把每个检测到的单元格块都导出到 `tables/*.csv`。不要把完整单元格块数据放进 JSON；在每个 `cellBlocks`、`tableAssets` 和 `metricAssets` 条目中存储 `dataPath` / `relativeDataPath` 指针。对于表格样式的块，还要写出原始 `table-assets/*.xlsx`，并存储 `tableWorkbookPath` / `relativeTableWorkbookPath`。

原始表格导出会有意保留图注行，以便追溯。后续生成应使用 `captionRows` 把这些行当作图片/表格图注，而不是可制图数据。

导出 CSV/XLSX 表格文件时，删除在检测块内部完全为空的列。把原始 Excel 范围保存在 `range` 中，并在 `removedBlankColumns` 中记录被删除的列位置，在 `exportedColCount` 中记录压缩后的列数。

第 1 步不要渲染图片、表格截图、图表图片或带样式视觉资产。渲染属于第 2 步。

使用以下 MVP 规则分类单元格块：

- `text_block`：3 行或更少的块、文本密集型块，或文本单元格占比至少 90% 的块。
- `data_table`：数值密集型块，或来自数据工作表的任意块。
- `metric_table`：紧凑的标签/数值样式块，混合文本和数字。
- `mixed_table`：含义不明确的块，留待后续复核或保守地插入表格。

如果某个表格样式块因为文本单元格超过 90% 而被重新分类为文本，不要为它创建 `table-assets/*.xlsx` 文件。文本仍保留在 JSON 中，CSV 副本仍保留在 `tables/` 下，确保源内容不丢失。

## 第 2A 步工作流

在渲染任何内容之前，先创建可编辑的视觉资产计划：

```bash
python path/to/ppt-template-generator/scripts/visual_asset_planner.py \
  project/intake/excel-content-manifest.json \
  --pretty
```

脚本写入：

```text
project/intake/
  visual-asset-plan.json
```

使用 `references/visual-asset-plan.schema.json` 作为第 2A 步契约。

第 2A 步不渲染 PNG 文件。它清洗表格资产，检测图注/标题/表头/数据行，推荐视觉类型，并选择样式来源。

第 2A 步表格路线决策：

- `source_image_route`：只有当已有 Excel 图片是合格的本地且内容感知匹配时，才优先使用该图片。合格源图片应位于同一工作表，在可能时与表格块有明确关系，并处于同一本地工作表区域：与表格范围重叠、共享同一行/列带，或在较小的行/列间距内呈对角邻近。还要比较表格侧文本（`blockId`、图注、表头、首列样本）和图片侧文本（`nearbyText` / 图注），并记录 `contentMatch.score` 以及匹配词。把所有评分候选记录到 `sourceImageCandidates`；只有 `sameSubsheetRegion=true` 且几何/内容支撑充分的候选，才应成为 `relatedImages`。
- `small_table_route`：小表格直接进入 `styled_table_image`；不要强制做成图表。
- `chart_route`：较大的表格分类为少量图表类别之一。

小表格规则：清洗后的数据行数和数据列数都必须小于或等于 8。

较大表格支持的第 2A 步图表类别：

- `trend_chart`：第一可用列类似日期/时间，后续列是数值序列。
- `category_chart`：第一可用列类似类别，后续列是数值。
- `composition_chart`：表格/图注/表头强调结构、配置、份额、分布、仓位、久期、市值区间或评级。
- `table_like_or_other`：不清楚的大型/混合表格；渲染为带样式表格图片，或送人工复核。

支持的第 2A 步视觉类型：

- `trend_chart`
- `category_chart`
- `composition_chart`
- `styled_table_image`
- `source_image`

表头检测必须可解释。计划中必须记录候选表头行、选中的 `header.excelRange`、`dataStartCsvRowIndex`、排除的图注/标题行、列画像、置信度和原因。

数据不应被静默丢弃。长图表应使用所有行，并通过坐标轴刻度稀疏或分页处理。较长的兜底表格应在后续分页为表格图片。

样式来源优先级：

- 图表：优先使用邻近/源 `image_asset_style`，其次是 `ppt_template_default`，最后是内置基金报告默认样式。
- 带样式表格图片：优先使用 `excel_table_style_or_ppt_default`，其次是邻近 `image_asset_style`，最后是 `ppt_template_default`。

## 第 2B 步工作流

根据第 2A 步计划渲染 Python 生成的视觉资产：

```bash
python path/to/ppt-template-generator/scripts/python_visual_renderer.py \
  project/intake/visual-asset-plan.json \
  --pretty
```

脚本写入：

```text
project/intake/
  python-table-assets.json
  python_table/
    <generated table/chart PNG files>
```

第 2B 步渲染按视觉类型模块化，而不是按单个表格模块化。把渲染器专用代码放在 `scripts/renderers/` 下：

- `table_image.py`：带样式的小表格/兜底表格图片。
- `trend_chart.py`：日期/时间序列图。
- `category_chart.py`：类别对比图。
- `composition_chart.py`：构成/配置图。

它会更新 `excel-content-manifest.json`，为对应的 `tableAssets`、匹配的 `cellBlocks` 和 `structuredContent.tables` 添加 `pythonVisualAssets` 与 `pythonVisualPath`。

对于使用 `source_image_route` 的表格资产，第 2B 步不创建 Python PNG。它写入 `selectedVisualAssets` / `selectedVisualPath`，指向相关的原始图片资产。对于已渲染的表格/图表资产，它同时写入 `selectedVisualAssets` 和 `pythonVisualAssets`。

旧版一体化视觉渲染路线和旧版 slide-plan 路线已移除。当前流程在第 2B 步后必须继续执行第 2C 步，再由第 3A 步生成 `ppt-generation-plan.json`。

## 第 2 步规则

- 保留 Excel 浮动图片为 `imageAssets`；第 2 步可以添加生成视觉资产，但不应删除原始图片资产。
- 不要为每个表格资产都生成图表。
- MVP 渲染器中不要使用堆叠条形图。对于 `composition_chart`，优先使用水平分组条形图，因为它更适合处理较长的中文类别标签，也更便于人工检查。
- 制图前，过滤空白/占位序列标签，例如空表头、`列7`、`行3`、`series 1` 或 `column 1`。如果没有有效序列，回退为带样式表格图片。
- 不要为了图表把缺失数值单元格填为 0。缺失数据应保持缺失，避免图表伪造柱形或折线。
- 不要在同一张图中混合不兼容单位。对于构成/配置图，优先选择类似比例的序列，例如贡献、收益率、增长、份额、占比和仓位；排除金额/市值类序列，例如 `金额`、`市值`、`万元`、`规模` 和 `价值`，除非没有更好的同质组。
- 把小型/混合/指标表格渲染为带样式表格 PNG。表头行和首列使用模板红，网格线使用浅灰，强调线使用金色。
- 在带样式表格 PNG 中，非整数数值单元格格式化为四位小数。看起来像百分比的单元格应保持百分比形式，也使用四位小数。
- 对带中文标签的带样式表格 PNG，为第一列预留额外宽度，并按字符换行 CJK 文本，避免产品/基金名称溢出或被裁切。
- 对带样式表格 PNG，检测简单的两行层级表头。如果第一条正文行是在空白/占位列下的纯文本子表头行，就合并父表头和子表头标签用于渲染，并从数据正文中移除该子表头行。把子标签放在前面，例如 `权益类\n资产配置比例(%)`，让窄 PPT 表格列中仍能看到子类别。
- 渲染用数值解析必须严格。不要从混合中文标签中抽取数字，例如以 `1期` 或 `2期` 结尾的产品名称；只有纯数值/百分比字符串才应格式化为数字。
- 根据哪种形式最清晰地传达数据，把较长的数值密集型表格转换为折线图、条形图或区间统计图。
- 对不清楚的表格，保留为人工复核参考，不要强行生成糟糕图表。
- 把文本备注作为要点或支持性文案纳入 `slide-plan.json`；不要因为文本来自单元格就丢弃它。
- 使用已解析模板注册表角色（`cover`、`toc`、`section`、`content`、`closing`）来选择模板源页。
- 把 `slide-plan.json` 视为可编辑文件。人工可以在第 3 步前重排幻灯片、删除生成图表或替换布局提示。

## 第 2C 步工作表 Markdown 资产

在重建第 3 步之前，从清洗后的 manifest 创建工作表级 Markdown 资产：

```bash
python path/to/ppt-template-generator/scripts/sheet_md_asset_builder.py \
  project/intake/excel-content-manifest.json \
  --pretty
```

脚本写入：

```text
project/intake/sheet-md-assets/
  sheet-md-manifest.json
  <sheet-name>.md
```

每个生成的工作表 Markdown 文件必须只包含重复出现的以下成对结构：

```markdown
## 观点文字资产

- <viewpoint text>

## 图片资产

- python_table/<image>.png
- picture-assets/<image>.png
```

如果某个工作表包含多个逻辑观点组，就在同一个 Markdown 文件中继续追加另一组 `## 观点文字资产` 和 `## 图片资产`。MVP 中不要引入嵌套小节结构，这样第 3 步可以顺序读取文件。

清洗规则：

- 保留 `excel-content-manifest.json` 中原始 `contentGroups` 顺序；该顺序遵循工作簿/工作表提取顺序。
- 只保留观点类文本块：投资观点、业绩评论、回顾结论、市场判断和策略说明。
- 丢弃仅标题块、纯图注、注释、备注、时间/数据范围、来源说明、表头和类似表格的数值行。
- 按 `●` 和 `■` 等项目符号切分观点文本。
- 如果某个工作表有明显的编号类别标题，例如 `1.`、`2、`、`3、`，强制这些标题成为内容块边界。后续观点文本和图片路径归入该编号块，直到下一个编号标题。
- 当源工作表有类别标题和图表/表格资产，但没有可用观点句时，编号块可以只包含 `## 图片资产`。
- 按邻近行顺序附加视觉路径。只包含现有 `python_table/` 和 `picture-assets/` 路径，并在每个工作表内部去重。
- 对于纯数据工作表，Markdown 文件只包含 `## 图片资产` 是有效的。

## 第 3A 步工作流

当前优先规划路线：从 `sheet-md-assets` 构建紧凑可编辑的 PPT 生成计划，而不是直接从原始 manifest 构建。

```bash
python path/to/ppt-template-generator/scripts/ppt_generation_plan_builder.py \
  project/intake \
  --template-id fund-pension-annuity \
  --pretty
```

脚本写入：

```text
project/intake/
  ppt-generation-plan.json
  ppt-generation-plan.md
```

在第 2C 步产出清洗后的逐工作表 Markdown 之后使用这条路线。它把 `sheet-md-assets/*.md` 作为内容真实来源，并保留 `sheet-md-manifest.json` 中的工作簿/工作表顺序。

第 3A 新版紧凑规划规则：

- `cover`、`toc` 和 `section` 幻灯片规划为只编辑文本，保留原生模板样式。
- `closing` 规划为不变。
- 内容页只在内容安全正文区域内半自由排版；模板标题、logo、页脚、红线、页码和其他版式外壳应由第 3B 步保留。
- 每张内容页应保持紧凑：最多 3 个视觉资产，最多 5 条展示要点。
- 同一工作表中的相邻 Markdown 块，在视觉和要点数量限制允许时，可以打包到同一张幻灯片。
- 如果某个 Markdown 块超过 3 张图片，把它拆分为紧凑视觉分块；未填满的最后一个纯视觉分块可以与下一个同工作表块合并。
- 如果某个 Markdown 块既有观点文本又有过多图片，不要创建溢出的纯图片内容页。只为同一张幻灯片选择关联性最强的图片，并把其余图片记录为 `deferredVisualAssets` 供人工复核。
- 该纯图片压缩规则不适用于只包含图片、不包含观点文本的 Markdown 块。这些仅图片块仍可生成纯视觉页。
- `displayText` 是可直接上幻灯片的精炼文本。`sourceText` 保留在 JSON 中，用于人工编辑和追溯。
- 如果 Markdown 内容块密度较低，目前上限为 3 条观点要点和 2 个视觉资产，不要压缩文本；只清理工作表元数据、占位标记、重复空格和明显行标签。只有对否则会挤满幻灯片的高密度内容块才使用压缩。
- Markdown 复核文件是用户的第一验收界面。在该计划被复核或明确接受之前，不要生成 PPT。

旧版基于 manifest 的 slide-plan 路线已移除。第 3A 步只使用 `ppt_generation_plan_builder.py` 生成 `ppt-generation-plan.json` 和 `ppt-generation-plan.md`。

第 3A 步文本规划规则：

- 在 intake manifest 中保留完整 Excel 文本，但为演示用途摘要化可见幻灯片文案。不要把很长的原始 Excel 段落直接倾倒到幻灯片上。
- 按 `●` 和 `■` 等项目符号切分文本备注，然后先过滤掉纯图注、备注、时间范围、数据范围和类似表格的数值字符串，再生成幻灯片要点。
- 长要点应缩短为面向听众的摘要，不要显示可见的 `...` 或 `…`。
- 当内容组有视觉资产时，优先创建紧凑页面：同一张幻灯片包含 2 到 4 条摘要要点和最多 3 个所选视觉资产。不要为了保留每句话而创建纯文本补充页。
- 当内容组没有视觉资产时，把摘要要点拆分到多张纯文本页，而不是丢弃它们。
- 保持要点顺序与 manifest/content group 顺序一致，使生成的 deck 遵循 Excel 派生资产的阅读顺序。

## 第 3B 步工作流

从 `ppt-generation-plan.json` 组合原生 PPTX 草稿；如果该文件不存在，才回退到旧版 `slide-plan.json`。生成流程必须离线可运行，不依赖 PowerPoint、WPS、Office COM 或图形界面。

默认生成路线：

```bash
python path/to/ppt-template-generator/scripts/pptx_step3b_composer.py \
  project/intake
```

脚本写入：

```text
project/intake/output/
  fund-pension-annuity-step3b-draft.pptx
  template-frame-map.json
  composition-report.json
```

第 3B 步消费：

- `ppt-generation-plan.json`，或旧版 `slide-plan.json`
- 所选模板的 `source.pptx`
- `python_table/` 渲染出的表格/图表 PNG
- 第 2 步选中的 `picture-assets/` 源 Excel 图片

组合器直接编辑 PPTX/OOXML 包，根据 `template-frame-map.json` 克隆模板源页，然后在内容区域内添加标题、要点和所选视觉资产。它应尽可能保留模板母版/背景/logo/页脚元素。内容页设计允许在安全内容区域内灵活处理，但第一个 MVP 应避免编辑模板外壳。

该基金年金模板的生成边界：

- `cover`、`toc` 和 `section` 幻灯片：只替换原始模板形状中的现有文本。不要添加白色遮罩、重绘背景、修改颜色或替换 logo/图片。
- `closing` 幻灯片：除非用户明确要求修改 closing 文本，否则保持不变。
- `content` 幻灯片：半自由设计只允许发生在正文/内容区域内。保留模板标题区域、红色下划线、logo/页脚、页码和其他外壳。
- 在向内容幻灯片添加生成内容之前，删除克隆模板页中的旧示例正文内容，例如旧文本块、表格、图表、图注和时间范围标签。不要删除标题或页码。
- 即使 JSON 中只有一个条目，也把 `visualAssets` 和 `bullets` 当作数组处理，确保单图页仍能收到其图片/表格。
- 使用 manifest 中的 `bullet.text` 或 plan 中的 `displayText`；绝不要把内部对象字符串写进 deck。
- 不要用 `...` 或 `…` 截断可见要点文本。如果文本过密，第 3A 步应把它拆分到额外幻灯片。
- 对同时有要点和视觉资产的内容页，使用浅灰摘要区域和紧凑视觉网格。全部内容都保持在模板标题下划线之下。
- 支持一个、两个和三个视觉资产的内容页。三个视觉资产页面可使用右上一个加底部两个的布局；两个视觉资产页面可使用摘要下方的底部双列布局。
- 默认不显示视觉图注。时间范围或表格备注等图注应留在可见幻灯片文案之外，除非人工明确要求。
- 插入图片时，在目标框内保持纵横比。绝不要为了填满框而拉伸图表/表格/源图片导致变形。
- 不要把 `_block_08` 等内部资产 ID 显示为可见图注，除非没有更好的人类可读图注且用户希望保留追溯信息。

组合后，至少验证：

- 输出 PPTX 存在，并且幻灯片数量与 `ppt-generation-plan.json` 或 `slide-plan.json` 预期一致
- PPTX 包内所有 `ppt/slides/*.xml.rels` 目标都存在
- `composition-report.json` 列出生成模式、已插入视觉资产和输出路径

可运行离线 QA：

```bash
python path/to/ppt-template-generator/scripts/pptx_step6_qa.py \
  project/intake
```

## 后续步骤

第 3 步应消费 `slide-plan.json`、`layout-registry.json` 和模板 `source.pptx`，通过克隆模板幻灯片来组合原生 PPTX。除非用户明确要求，否则生成的 PPT 必须保留模板母版/背景/logo/页脚元素，并且只在内容区域内设计。

## 日志

维护该 skill 文件夹中的 `WORK_LOG.txt`。每个实现步骤后追加一条简短记录，包括修改内容、运行的验证和已知限制。
