#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import PptxGenJS from "pptxgenjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const skillRoot = path.resolve(__dirname, "..");

const args = parseArgs(process.argv.slice(2));
const manifestPath = args.manifest;
const outPath = args.out;
const themePath =
  args.theme || path.join(skillRoot, "native_templates", "templates.json");

if (!manifestPath || !outPath) {
  fail(
    "Usage: node scripts/build_native_pptx_dynamic.mjs --manifest <manifest.json> --out <deck.pptx> [--theme <templates.json>]"
  );
}

const manifest = readJson(manifestPath);
const themeLibrary = readJson(themePath);
validateManifest(manifest);

const pptx = new PptxGenJS();
pptx.layout = themeLibrary.canvas?.layout || "LAYOUT_WIDE";
pptx.author = "codex-ppt Route B dynamic native builder";
pptx.subject = "Dynamic native editable rebuild";
pptx.title = manifest.deck?.title || "Native Editable Deck";
pptx.company = "codex-ppt";
const SHAPE_TYPES = pptx.ShapeType || {};

const ctx = {
  pptx,
  fontFace: manifest.deck?.fontFace || themeLibrary.theme?.fontFace || "Microsoft YaHei",
  colors: themeLibrary.theme?.colors || defaultColors(),
  deck: manifest.deck || {},
  canvas: { width: 13.333, height: 7.5 }
};

pptx.theme = {
  headFontFace: ctx.fontFace,
  bodyFontFace: ctx.fontFace,
  lang: "zh-CN"
};

const usedLayouts = [];
for (const slidePlan of manifest.slides) {
  const plan = normalizeSlidePlan(slidePlan);
  usedLayouts.push(plan.layout_type);
  const slide = pptx.addSlide();
  slide.background = { color: ctx.colors.white };
  renderChrome(slide, plan, ctx);

  switch (plan.layout_type) {
    case "auto_hub_spoke":
      renderAutoHubSpoke(slide, plan, ctx);
      break;
    case "auto_cards":
      renderAutoCards(slide, plan, ctx);
      break;
    case "auto_process":
      renderAutoProcess(slide, plan, ctx);
      break;
    case "auto_matrix":
      renderAutoMatrix(slide, plan, ctx);
      break;
    case "auto_layers":
      renderAutoLayers(slide, plan, ctx);
      break;
    case "auto_two_column":
      renderAutoTwoColumn(slide, plan, ctx);
      break;
    default:
      fail(`Unsupported layout_type: ${plan.layout_type}`);
  }

  renderTakeaway(slide, plan, ctx);
  if (plan.notes && typeof slide.addNotes === "function") {
    slide.addNotes(String(plan.notes).split(/\r?\n/));
  }
}

fs.mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
await pptx.writeFile({ fileName: outPath });
console.log(
  JSON.stringify(
    {
      ok: true,
      output: path.resolve(outPath),
      slides: manifest.slides.length,
      layouts: [...new Set(usedLayouts)]
    },
    null,
    2
  )
);

function renderChrome(slide, plan, ctx) {
  const c = ctx.colors;
  rect(slide, { x: 0.55, y: 0.42, w: 0.42, h: 0.42 }, { fill: c.deepRed, line: c.deepRed });
  text(slide, "-", { x: 0.62, y: 0.52, w: 0.28, h: 0.18 }, { size: 18, bold: true, color: c.white, align: "center", margin: 0 }, ctx);
  text(slide, ctx.deck.title || plan.deck_title || "", { x: 1.08, y: 0.43, w: 5.95, h: 0.42 }, { size: 15, bold: true, fit: "shrink" }, ctx);
  text(slide, plan.eyebrow || ctx.deck.eyebrow || "", { x: 9.7, y: 0.45, w: 3, h: 0.26 }, { size: 7, bold: true, color: c.deepRed, align: "right", fit: "shrink" }, ctx);
  text(slide, plan.title, { x: 0.9, y: 1.03, w: 11.5, h: 0.55 }, { size: 24, bold: true, fit: "shrink" }, ctx);
  if (plan.subtitle) {
    text(slide, plan.subtitle, { x: 0.93, y: 1.65, w: 10.8, h: 0.3 }, { size: 9.5, color: c.muted, fit: "shrink" }, ctx);
  }
}

function renderAutoCards(slide, plan, ctx) {
  const items = pickItems(plan).slice(0, 8);
  const area = contentArea(plan);
  const grid = gridSlots(area, items.length, { maxCols: items.length === 4 ? 2 : 3, gapX: 0.32, gapY: 0.34 });
  items.forEach((item, index) => {
    riskCard(slide, grid[index], item, toneAt(item, index), ctx);
  });
}

function renderAutoHubSpoke(slide, plan, ctx) {
  const c = ctx.colors;
  const items = pickItems(plan).slice(0, 8);
  const centerBox = { x: 5.68, y: 3.0, w: 1.98, h: 1.45 };
  const itemSlots = radialSlots(items.length, {
    cx: centerBox.x + centerBox.w / 2,
    cy: centerBox.y + centerBox.h / 2,
    rx: 4.05,
    ry: 1.8,
    cardW: items.length <= 5 ? 2.45 : 2.22,
    cardH: 0.82
  });

  const axis = plan.axis_labels || {};
  if (axis.left || axis.right || axis.bottom) {
    line(slide, { x: 2.08, y: 4.0, w: 9.1, h: 0 }, { color: c.gold, width: 0.9 });
    line(slide, { x: 6.67, y: 2.12, w: 0, h: 3.85 }, { color: "BABABA", width: 0.7 });
    text(slide, axis.left || "", { x: 1.05, y: 3.82, w: 1.6, h: 0.32 }, { size: 13, bold: true, align: "center", fit: "shrink" }, ctx);
    text(slide, axis.right || "", { x: 10.7, y: 3.82, w: 1.6, h: 0.32 }, { size: 13, bold: true, align: "center", fit: "shrink" }, ctx);
    text(slide, axis.bottom || "", { x: 6.02, y: 6.25, w: 1.35, h: 0.32 }, { size: 13, bold: true, align: "center", fit: "shrink" }, ctx);
  }

  if (plan.connector_policy === "minimal" && items.length <= 6) {
    itemSlots.forEach((slot) => {
      const from = nearestEdgePoint(slot, center(centerBox));
      const to = nearestEdgePoint(centerBox, center(slot));
      line(slide, { x: from.x, y: from.y, w: to.x - from.x, h: to.y - from.y }, { color: c.line, width: 0.65 });
    });
  }

  shape(slide, "hexagon", centerBox, { fill: c.deepRed, line: c.deepRed });
  text(slide, join(plan.center?.title || plan.center || "Center", plan.center?.body), inset(centerBox, 0.13, 0.16), {
    size: 17,
    bold: true,
    color: c.white,
    align: "center",
    valign: "mid",
    fit: "shrink"
  }, ctx);
  items.forEach((item, index) => riskCard(slide, itemSlots[index], item, toneAt(item, index), ctx));
}

function renderAutoProcess(slide, plan, ctx) {
  const c = ctx.colors;
  const steps = (plan.steps || plan.items || []).slice(0, 7);
  const area = { x: 0.92, y: 2.55, w: 11.5, h: 1.7 };
  const gap = 0.2;
  const stepW = (area.w - gap * Math.max(steps.length - 1, 0)) / Math.max(steps.length, 1);
  steps.forEach((step, index) => {
    const box = { x: area.x + index * (stepW + gap), y: area.y, w: stepW, h: area.h };
    rounded(slide, box, { fill: index % 2 ? c.soft : c.cream, line: "E0D7C8" });
    text(slide, String(step.number ?? index + 1).padStart(2, "0"), { x: box.x + 0.16, y: box.y + 0.16, w: 0.36, h: 0.22 }, { size: 10, bold: true, color: c.gold }, ctx);
    text(slide, step.title || "", { x: box.x + 0.52, y: box.y + 0.15, w: box.w - 0.68, h: 0.34 }, { size: 11.5, bold: true, fit: "shrink" }, ctx);
    text(slide, step.body || "", { x: box.x + 0.2, y: box.y + 0.66, w: box.w - 0.4, h: 0.65 }, { size: 8.3, color: c.muted, fit: "shrink" }, ctx);
    if (index < steps.length - 1) {
      line(slide, { x: box.x + box.w + 0.03, y: box.y + box.h / 2, w: gap - 0.06, h: 0 }, { color: c.gold, width: 1.1, endArrowType: "triangle" });
    }
  });
}

function renderAutoMatrix(slide, plan, ctx) {
  const rows = (plan.rows || plan.items || []).slice(0, 7);
  const columns = plan.columns || [
    { key: "risk", label: "Risk", width: 0.32 },
    { key: "impact", label: "Impact", width: 0.22 },
    { key: "control", label: "Control", width: 0.46 }
  ];
  const box = { x: 0.92, y: 2.15, w: 11.5, h: 4.0 };
  renderTable(slide, box, columns, rows, ctx);
}

function renderAutoLayers(slide, plan, ctx) {
  const c = ctx.colors;
  const layers = (plan.layers || plan.items || []).slice(0, 6);
  const startW = 11.1;
  const h = Math.min(0.72, 3.9 / Math.max(layers.length, 1));
  const gap = 0.15;
  layers.forEach((layer, index) => {
    const w = startW - index * 0.58;
    const box = { x: (13.333 - w) / 2, y: 2.12 + index * (h + gap), w, h };
    const fill = [c.deepRed, c.gray, c.gold, c.cream, c.soft, "FFFFFF"][index] || c.soft;
    const dark = index < 3;
    rounded(slide, box, { fill, line: dark ? fill : "E0D7C8" });
    text(slide, layer.title || "", { x: box.x + 0.22, y: box.y + 0.15, w: 2.3, h: 0.32 }, { size: 11.5, bold: true, color: dark ? c.white : c.ink, fit: "shrink" }, ctx);
    text(slide, layer.body || "", { x: box.x + 2.65, y: box.y + 0.16, w: box.w - 2.95, h: 0.32 }, { size: 8.8, color: dark ? c.white : c.muted, fit: "shrink" }, ctx);
  });
}

function renderAutoTwoColumn(slide, plan, ctx) {
  const c = ctx.colors;
  const left = plan.left || { title: plan.claim_title || "Claim", items: plan.claims || [] };
  const right = plan.right || { title: plan.evidence_title || "Evidence", items: plan.evidence || [] };
  const boxes = [
    { x: 0.92, y: 2.12, w: 5.45, h: 3.95 },
    { x: 6.95, y: 2.12, w: 5.45, h: 3.95 }
  ];
  [left, right].forEach((col, i) => {
    rounded(slide, boxes[i], { fill: i ? c.soft : c.cream, line: "E0D7C8" });
    text(slide, col.title || "", { x: boxes[i].x + 0.26, y: boxes[i].y + 0.22, w: boxes[i].w - 0.52, h: 0.36 }, { size: 14, bold: true, fit: "shrink" }, ctx);
    const list = Array.isArray(col.items) ? col.items.slice(0, 5) : [];
    list.forEach((item, idx) => {
      const y = boxes[i].y + 0.82 + idx * 0.58;
      text(slide, `${idx + 1}. ${typeof item === "string" ? item : item.title || item.body || ""}`, { x: boxes[i].x + 0.34, y, w: boxes[i].w - 0.7, h: 0.42 }, { size: 9.8, color: c.ink, fit: "shrink" }, ctx);
    });
  });
}

function renderTakeaway(slide, plan, ctx) {
  if (!plan.takeaway) return;
  rounded(slide, { x: 0.92, y: 6.55, w: 11.5, h: 0.5 }, { fill: ctx.colors.soft, line: "E5E7EB" });
  text(slide, plan.takeaway, { x: 1.16, y: 6.66, w: 10.9, h: 0.25 }, { size: 13.5, bold: true, fit: "shrink" }, ctx);
}

function renderTable(slide, box, columns, rows, ctx) {
  const c = ctx.colors;
  const headerH = 0.42;
  const rowH = (box.h - headerH) / Math.max(rows.length, 1);
  rounded(slide, box, { fill: c.white, line: "E5E7EB" });
  let x = box.x;
  columns.forEach((col) => {
    const w = box.w * col.width;
    rect(slide, { x, y: box.y, w, h: headerH }, { fill: c.deepRed, line: c.deepRed });
    text(slide, col.label, { x: x + 0.08, y: box.y + 0.08, w: w - 0.16, h: headerH - 0.12 }, { size: 8.8, bold: true, color: c.white, fit: "shrink" }, ctx);
    x += w;
  });
  rows.forEach((row, rowIndex) => {
    let colX = box.x;
    const y = box.y + headerH + rowIndex * rowH;
    columns.forEach((col, colIndex) => {
      const w = box.w * col.width;
      rect(slide, { x: colX, y, w, h: rowH }, { fill: rowIndex % 2 ? c.white : "FBFAF7", line: "E5E0D6" });
      text(slide, row[col.key] || row.title || row.body || "", { x: colX + 0.1, y: y + 0.08, w: w - 0.2, h: rowH - 0.14 }, {
        size: colIndex === 0 ? 9.7 : 8.3,
        bold: colIndex === 0,
        fit: "shrink"
      }, ctx);
      colX += w;
    });
  });
}

function riskCard(slide, box, item, tone, ctx) {
  const c = ctx.colors;
  const fill = c[tone] || c.soft;
  const dark = ["red", "deepRed", "gray"].includes(tone);
  rounded(slide, box, { fill, line: dark ? fill : "DED8CE" });
  text(slide, String(item.number ?? "").padStart(2, "0"), { x: box.x + 0.16, y: box.y + 0.18, w: 0.4, h: 0.22 }, { size: 10, bold: true, color: dark ? c.sand : c.gold, fit: "shrink" }, ctx);
  text(slide, item.title || "", { x: box.x + 0.58, y: box.y + 0.16, w: box.w - 0.76, h: 0.3 }, { size: 11, bold: true, color: dark ? c.white : c.ink, fit: "shrink" }, ctx);
  text(slide, item.body || "", { x: box.x + 0.58, y: box.y + 0.5, w: box.w - 0.76, h: box.h - 0.58 }, { size: 7.6, color: dark ? "F3F4F6" : c.muted, fit: "shrink" }, ctx);
}

function normalizeSlidePlan(plan) {
  if (!plan.layout_type) {
    if (plan.template_id?.includes("matrix") || plan.rows) plan.layout_type = "auto_matrix";
    else if (plan.template_id?.includes("process") || plan.steps) plan.layout_type = "auto_process";
    else if (plan.template_id?.includes("layers") || plan.layers) plan.layout_type = "auto_layers";
    else if (plan.center) plan.layout_type = "auto_hub_spoke";
    else plan.layout_type = "auto_cards";
  }
  return plan;
}

function validateManifest(manifest) {
  if (!manifest || !Array.isArray(manifest.slides) || manifest.slides.length === 0) {
    fail("Manifest must contain a non-empty slides array.");
  }
  manifest.slides.forEach((slide, idx) => {
    if (!slide.title) fail(`Slide ${idx + 1} is missing title.`);
    if (!slide.layout_type && !slide.template_id) fail(`Slide ${idx + 1} needs layout_type or template_id.`);
  });
}

function contentArea() {
  return { x: 0.92, y: 2.15, w: 11.5, h: 3.95 };
}

function gridSlots(area, count, options = {}) {
  const maxCols = options.maxCols || 3;
  const cols = Math.min(maxCols, Math.max(1, count <= 2 ? count : Math.ceil(Math.sqrt(count + 1))));
  const rows = Math.ceil(count / cols);
  const gapX = options.gapX || 0.28;
  const gapY = options.gapY || 0.28;
  const w = (area.w - gapX * (cols - 1)) / cols;
  const h = Math.min(1.25, (area.h - gapY * (rows - 1)) / rows);
  const totalH = h * rows + gapY * (rows - 1);
  const startY = area.y + Math.max(0, (area.h - totalH) / 2);
  return Array.from({ length: count }, (_, i) => ({
    x: area.x + (i % cols) * (w + gapX),
    y: startY + Math.floor(i / cols) * (h + gapY),
    w,
    h
  }));
}

function radialSlots(count, options) {
  if (count <= 0) return [];
  const angleSets = {
    1: [-90],
    2: [180, 0],
    3: [210, -90, -30],
    4: [210, 150, 30, -30],
    5: [210, 165, -90, 15, -30],
    6: [210, 160, -90, -20, 25, 330],
    7: [210, 170, 130, -90, -40, 0, 35],
    8: [215, 180, 145, -90, -35, 0, 35, 325]
  };
  const angles = angleSets[count] || Array.from({ length: count }, (_, i) => -90 + (360 / count) * i);
  return angles.map((deg) => {
    const rad = (Math.PI / 180) * deg;
    const x = options.cx + Math.cos(rad) * options.rx - options.cardW / 2;
    const y = options.cy + Math.sin(rad) * options.ry - options.cardH / 2;
    return clampBox({ x, y, w: options.cardW, h: options.cardH }, { x: 0.9, y: 1.98, w: 11.55, h: 4.18 });
  });
}

function clampBox(box, bounds) {
  return {
    ...box,
    x: Math.min(Math.max(box.x, bounds.x), bounds.x + bounds.w - box.w),
    y: Math.min(Math.max(box.y, bounds.y), bounds.y + bounds.h - box.h)
  };
}

function pickItems(plan) {
  return Array.isArray(plan.items) ? plan.items : [];
}

function toneAt(item, index) {
  return item.tone || ["gray", "red", "cream", "cream", "sand", "soft", "gold", "deepRed"][index] || "soft";
}

function rounded(slide, box, opts = {}) {
  shape(slide, "roundRect", box, opts);
}

function rect(slide, box, opts = {}) {
  shape(slide, "rect", box, opts);
}

function shape(slide, kind, box, opts = {}) {
  if (!box) return;
  slide.addShape(shapeType(kind), {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    rectRadius: 0.12,
    fill: opts.fill ? { color: opts.fill, transparency: opts.transparency || 0 } : undefined,
    line: opts.line === false ? { transparency: 100 } : { color: opts.line || "D9D4CA", width: opts.width || 0.8 }
  });
}

function text(slide, value, box, opts, ctx) {
  if (!box || value === undefined || value === null || value === "") return;
  slide.addText(String(value), {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fontFace: ctx.fontFace,
    fontSize: opts.size || 10,
    bold: Boolean(opts.bold),
    color: opts.color || ctx.colors.ink,
    align: opts.align || "left",
    valign: opts.valign || "top",
    margin: opts.margin ?? 0.03,
    fit: opts.fit || "shrink",
    breakLine: false
  });
}

function line(slide, box, opts = {}) {
  const lineOpts = { color: opts.color || "C7C1B5", width: opts.width || 0.8 };
  if (opts.endArrowType) lineOpts.endArrowType = opts.endArrowType;
  slide.addShape(shapeType("line"), { x: box.x, y: box.y, w: box.w, h: box.h, line: lineOpts });
}

function shapeType(kind) {
  if (kind === "roundRect") return SHAPE_TYPES.roundRect || SHAPE_TYPES.rect || "roundRect";
  if (kind === "hexagon") return SHAPE_TYPES.hexagon || SHAPE_TYPES.rect || "hexagon";
  if (kind === "line") return SHAPE_TYPES.line || "line";
  return SHAPE_TYPES.rect || "rect";
}

function center(box) {
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

function nearestEdgePoint(box, target) {
  const c = center(box);
  const dx = target.x - c.x;
  const dy = target.y - c.y;
  const scale = Math.max(Math.abs(dx) / (box.w / 2), Math.abs(dy) / (box.h / 2), 1);
  return { x: c.x + dx / scale, y: c.y + dy / scale };
}

function inset(box, dx, dy) {
  return {
    x: box.x + dx,
    y: box.y + dy,
    w: Math.max(0.05, box.w - dx * 2),
    h: Math.max(0.05, box.h - dy * 2)
  };
}

function join(title, body) {
  return body ? `${title}\n${body}` : String(title || "");
}

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) parsed[key] = true;
    else {
      parsed[key] = next;
      i += 1;
    }
  }
  return parsed;
}

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    fail(`Cannot read JSON ${filePath}: ${error.message}`);
  }
}

function defaultColors() {
  return {
    ink: "111111",
    muted: "6B7280",
    line: "C7C1B5",
    deepRed: "7A0710",
    red: "B3041B",
    gray: "6F6F72",
    gold: "C3A15D",
    sand: "E1C991",
    cream: "F4EFE5",
    soft: "F8F7F4",
    white: "FFFFFF"
  };
}

function fail(message) {
  console.error(message);
  process.exit(1);
}
