---
name: markdown-report-skill
version: 1.0.0
description: Generate Markdown papers and reports
owner: AI Desktop System
lifecycle: stable
risk_level: low
trigger:
  - 生成报告
  - 生成论文
  - Markdown
  - 论文
  - 报告
permissions:
  file_write: true
  command_exec: false
  network: false
dependencies: []
constraints:
  - 禁止在内容中插入未转义的 HTML/脚本
  - 图片必须是可访问的本地路径
  - 不支持嵌入二进制附件
references:
  - Markdown 指南: https://www.markdownguide.org
  - GFM 规范: https://github.github.com/gfm
limitations:
  - 不包含高级排版（如页眉页脚、分页）
  - 复杂公式建议使用 LaTeX 数学表达式语法
  - 生成结果需在支持 Markdown 的编辑器中预览
validation:
  - Markdown 文档无错误生成
  - 所有标题使用正确 markdown 语法
  - 表格为有效 markdown 格式
  - 图片引用正确
workflow:
  - 1. 解析输入: 标题、作者、章节、表格、图片
  - 2. 生成文档头部（标题）
  - 3. 用 GFM markdown 标题生成各章节（#~#### 最多4级）
  - 4. 插入 markdown 表格
  - 5. 插入行内图片（不编号）
  - 6. 添加简单参考文献
  - 7. 保存为 .md 文件
---

# Markdown Report Skill

生成 Markdown 论文、报告。无需外部编译（区别于 LaTeX），直接输出 .md 文件。

## 定位

轻量化、线上阅读优先、适合快速迭代、技术向文稿；不追求公文式严格排版，侧重可读性、信息密度。

## 强制写作标准

1. **语法规范**：严格标准 GitHub Flavored Markdown（GFM）
   - 标题层级：# ~ #### 最多 4 级标题，禁止无层级乱写
   - 公式：使用 `$` 行内公式 / `$$` 块公式
   - 代码：```` ```language ```` 带语言标记代码块
   - 表格、列表、引用块统一标准写法
2. **内容结构通用范式（按需裁剪，不硬塞）**：
   ```
   # 标题
   ## 1 概述
   ## 2 方案/原理
   ## 3 实验设置
   ## 4 结果与分析
   ## 5 总结与后续计划
   ```
3. **行文约束**：
   - 文字精炼，减少冗余套话；重点数据加粗
   - 不生成页眉、页码、正式图号表号、严格 GB/T 7714 参考文献
   - 面向开发者/技术人员，文风偏技术笔记

## 内置写作指令

> 你将使用标准GFM Markdown撰写报告。
> 1. 标题层级最多4级，合理划分章节；支持行内/块公式、带标记代码块、Markdown表格；
> 2. 行文简洁，侧重技术逻辑与数据展示；
> 3. 无需生成正式图编号、表编号，不需要严格GB/T7714参考文献格式；
> 4. 输出内容仅Markdown文本，不输出额外无关说明。
