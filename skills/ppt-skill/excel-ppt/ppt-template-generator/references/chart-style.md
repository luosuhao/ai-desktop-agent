# Chart and Table Style Reference

Use this reference in Step 2 when classifying and rendering visual assets from Excel table assets.

## Visual Direction

Match the existing fund pension annuity PPT visual language:

- White background, quiet grid, high whitespace.
- Primary emphasis red: `#9E0116`.
- Secondary accent gold: `#BF9D5A`.
- Neutral grays: `#D9D9D9`, `#A6A6A6`, `#666666`.
- Main text: near black `#111111`.
- Use one strong red series, one gold series, then gray series. Avoid rainbow palettes.
- Keep charts clean enough to sit inside the native PPT content layout without fighting the template logo, footer, and page number.

## Asset Selection Rules

- Do not render every table as a chart.
- Small or mixed tables: render a styled table PNG.
- Metric-like compact blocks: render a styled table PNG unless a KPI card style is added later.
- Long date/time-like numeric data: render a line chart. Use the full data range with downsampling when needed, not only the latest rows.
- Long non-date numeric data: render an interval/statistics bar chart instead of a giant table.
- Short numeric category data: render a bar chart only when it is clearer than a table.
- Unclear or non-numeric tables: keep as a reference-only table asset for human review.
- Existing Excel floating chart images should be preserved as image assets; do not replace them unless a generated chart is explicitly better.

## Table Direction

For rendered table images and Step 3 direct table insertion, follow the same palette:

- Header fill red, white bold header text.
- First column fill red when it acts as row headers, with white bold text.
- Thin gold top/bottom rule where useful.
- Light gray internal grid.
- Right-align numbers and left-align labels.
- Keep direct tables small. Long data tables should become charts, reference-only assets, or be split across slides.

## Style Presets

Store style choices in `visual-assets.json` so a later AI or human review step can choose or override them:

- `fund_report_table`: red header/first-column table, gray grid, gold accent.
- `fund_report_clean`: clean chart with red primary series, gold secondary series, gray supporting series.

## Limits

Step 2 renders PNG visual assets and an editable `slide-plan.json`.
Final native PPT composition is Step 3.
