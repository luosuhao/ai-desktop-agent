---
name: word-lab-report-skill
version: 1.0.0
description: Generate Word lab reports with cover, TOC, tables, and figures
owner: AI Desktop System
lifecycle: stable
risk_level: low
trigger:
  - 生成Word
  - 实验报告
  - Word报告
  - 文档
permissions:
  file_write: true
  command_exec: false
  network: false
dependencies:
  - python-docx
constraints:
  - 文件名需过滤特殊字符
  - 禁止写入系统目录
  - 图片必须是支持的格式
references:
  - python-docx 文档: https://python-docx.readthedocs.io
limitations:
  - 复杂排版需手动调整
  - 不支持 .doc 旧格式
  - 嵌入图片需本地路径
validation:
  - 文档无错误生成
  - 所有标题使用正确样式
  - 表格格式正确
  - 图片正确嵌入
workflow:
  - 1. 解析输入: 标题、作者、章节、表格、图片
  - 2. 生成封面页
  - 3. 生成目录页（数字编号）
  - 4. 生成各章节正文（1/1.1/1.1.1 自动编号）
  - 5. 插入表格（表X 标题在上方）和图片（图X 标题在下方）
  - 6. 添加参考文献（GB/T 7714）
  - 7. 保存为 .docx 文件
---

# Word Lab Report Skill

生成 Word 实验报告，包含封面页、目录页、格式化章节、表格和图片。

## 定位

线下正式归档、学校/实验室硬性格式要求；输出文本完全适配导入 Word 进行标准化排版，满足纸质提交、归档审核。

## 强制写作标准

1. **结构规范（固定正式报告层级，严格章节编号）**：
   ```
   1 绪论（一级标题）
     1.1 研究背景（二级标题）
     1.2 实验目的
   2 实验原理
   3 实验环境与方案
     3.1 软硬件环境
     3.2 实验步骤
   4 实验结果与数据分析
   5 实验讨论、误差分析
   6 实验结论
   参考文献
   附录（可选）
   ```
2. **图文标注硬性规则**：
   - 所有图片统一规范文字：**图1 XXXX（图题置于图下方）**
   - 所有表格统一规范文字：**表1 XXXX（表题置于表上方）**
3. **参考文献标准**：默认遵循 GB/T 7714 规范格式
4. **行文约束**：
   - 使用正式学术书面语，增加规范过渡语句
   - 预留足够段落间距逻辑，方便后续在 Word 里设置样式
   - **不输出 Markdown 语法**，纯结构化正文文本
   - 禁止代码块大量堆砌，代码统一放进附录

## 内置写作指令

> 你将撰写适配Microsoft Word排版的正式实验室实验报告，只输出纯正文文本，禁止Markdown语法。
> 1. 严格使用 1 / 1.1 / 1.1.1 多级数字章节编号；
> 2. 图片标注统一为「图X 标题」放在图片下方；表格标注统一为「表X 标题」放在表格上方；
> 3. 参考文献按照 GB/T 7714 格式撰写；
> 4. 使用规范学术书面语，遵循标准实验报告完整框架：绪论→原理→实验方案→结果分析→结论。
