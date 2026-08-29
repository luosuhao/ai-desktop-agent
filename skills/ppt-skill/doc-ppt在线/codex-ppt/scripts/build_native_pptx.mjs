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
const templatePath =
  args.templates || path.join(skillRoot, "native_templates", "templates.json");

if (!manifestPath || !outPath) {
  fail(
    "Usage: node scripts/build_native_pptx.mjs --manifest <manifest.json> --out <deck.pptx> [--templates <templates.json>]"
  );
}

const manifest = readJson(manifestPath);
const library = readJson(templatePath);
const templates = new Map(library.templates.map((tpl) => [tpl.template_id, tpl]));

validateManifest(manifest, templates);

const pptx = new PptxGenJS();
pptx.layout = library.canvas?.layout || "LAYOUT_WIDE";
pptx.author = "codex-ppt Route B";
pptx.subject = "Native editable rebuild";
pptx.title = manifest.deck?.title || "Native Editable Deck";
pptx.company = "codex-ppt";
const SHAPE_TYPES = pptx.ShapeType || {};
pptx.theme = {
  headFontFace: manifest.deck?.fontFace || library.theme?.fontFace || "Microsoft YaHei",
  bodyFontFace: manifest.deck?.fontFace || library.theme?.fontFace || "Microsoft YaHei",
  lang: "zh-CN"
};

const ctx = {
  colors: library.theme?.colors || {},
  fontFace: manifest.deck?.fontFace || library.theme?.fontFace || "Microsoft YaHei",
  deck: manifest.deck || {},
  pptx
};

for (const slideData of manifest.slides) {
  const template = templates.get(slideData.template_id);
  const slide = pptx.addSlide();
  slide.background = { color: ctx.colors.white || "FFFFFF" };
  renderChrome(slide, template, slideData, ctx);

  switch (slideData.template_id) {
    case "six_risk_hub_spoke_clean":
      renderSixRiskHub(slide, template, slideData, ctx);
      break;
    case "six_cards_grid":
      renderSixCards(slide, template, slideData, ctx);
      break;
    case "risk_control_matrix":
      renderRiskControlMatrix(slide, template, slideData, ctx);
      break;
    case "lifecycle_process":
      renderLifecycleProcess(slide, template, slideData, ctx);
      break;
    case "governance_layers":
      renderGovernanceLayers(slide, template, slideData, ctx);
      break;
    default:
      fail(`Unsupported template_id: ${slideData.template_id}`);
  }

  if (slideData.notes && typeof slide.addNotes === "function") {
    slide.addNotes(String(slideData.notes).split(/\r?\n/));
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
      templates: [...new Set(manifest.slides.map((s) => s.template_id))]
    },
    null,
    2
  )
);

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      parsed[key] = true;
    } else {
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

function validateManifest(manifest, templates) {
  if (!manifest || !Array.isArray(manifest.slides) || manifest.slides.length === 0) {
    fail("Manifest must contain a non-empty slides array.");
  }
  manifest.slides.forEach((slide, idx) => {
    if (!slide.template_id) fail(`Slide ${idx + 1} is missing template_id.`);
    if (!templates.has(slide.template_id)) {
      fail(`Slide ${idx + 1} uses unknown template_id: ${slide.template_id}`);
    }
    if (!slide.title) fail(`Slide ${idx + 1} is missing title.`);
  });
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

function renderChrome(slide, template, data, ctx) {
  const s = template.slots;
  const colors = ctx.colors;
  addShape(slide, "rect", s.header_mark, {
    fill: colors.deepRed,
    line: colors.deepRed
  });
  addText(slide, "-", inset(s.header_mark, 0.08, 0.13), {
    color: colors.white,
    fontSize: 18,
    bold: true,
    align: "center",
    valign: "mid",
    margin: 0
  }, ctx);
  addText(slide, ctx.deck.title || data.deck_title || "", s.deck_title, {
    fontSize: 15,
    bold: true,
    color: colors.ink,
    fit: "shrink"
  }, ctx);
  addText(slide, data.eyebrow || ctx.deck.eyebrow || "", s.eyebrow, {
    fontSize: 7,
    bold: true,
    color: colors.deepRed,
    align: "right",
    fit: "shrink"
  }, ctx);
  addText(slide, data.title || "", s.title, {
    fontSize: 24,
    bold: true,
    color: colors.ink,
    align: s.title.x > 2 ? "center" : "left",
    fit: "shrink"
  }, ctx);
  if (data.subtitle && s.subtitle) {
    addText(slide, data.subtitle, s.subtitle, {
      fontSize: 9.5,
      color: colors.muted,
      align: s.subtitle.x > 2 ? "center" : "left",
      fit: "shrink"
    }, ctx);
  }
  if (data.takeaway && s.takeaway) {
    addShape(slide, "roundRect", s.takeaway, {
      fill: colors.soft,
      line: "E5E7EB",
      radius: 0.12
    });
    addText(slide, data.takeaway, inset(s.takeaway, 0.22, 0.08), {
      fontSize: 14,
      bold: true,
      color: colors.ink,
      fit: "shrink"
    }, ctx);
  }
}

function renderSixRiskHub(slide, template, data, ctx) {
  const s = template.slots;
  const colors = ctx.colors;
  const items = (data.items || []).slice(0, 6);

  addLine(slide, { x: 2.1, y: 4.02, w: 9.1, h: 0 }, colors.gold, 1);
  addLine(slide, { x: 6.66, y: 2.1, w: 0, h: 3.9 }, "B8B8B8", 0.75);

  if (data.axis_labels) {
    addText(slide, data.axis_labels.left || "", s.axis_left, axisText(), ctx);
    addText(slide, data.axis_labels.right || "", s.axis_right, axisText(), ctx);
    addText(slide, data.axis_labels.bottom || "", s.axis_bottom, axisText(), ctx);
  }

  if (data.connectors === true) {
    items.forEach((item, index) => {
      const slot = s[`item_${index + 1}`];
      addLineBetweenSlots(slide, slot, s.center, colors.line, 0.8);
    });
  }

  addShape(slide, "hexagon", s.center, {
    fill: colors.deepRed,
    line: colors.deepRed
  });
  addText(slide, joinText(data.center?.title || data.center || "Center", data.center?.body), inset(s.center, 0.12, 0.18), {
    fontSize: 17,
    bold: true,
    color: colors.white,
    align: "center",
    valign: "mid",
    fit: "shrink"
  }, ctx);

  items.forEach((item, index) => {
    const slot = s[`item_${index + 1}`];
    const tone = item.tone || ["gray", "red", "cream", "cream", "sand", "soft"][index] || "soft";
    addRiskCard(slide, slot, item, tone, ctx);
  });
}

function renderSixCards(slide, template, data, ctx) {
  const items = (data.items || []).slice(0, 6);
  items.forEach((item, index) => {
    const tone = item.tone || ["red", "gray", "deepRed", "gold", "sand", "soft"][index] || "soft";
    addRiskCard(slide, template.slots[`item_${index + 1}`], item, tone, ctx);
  });
}

function renderRiskControlMatrix(slide, template, data, ctx) {
  const rows = (data.rows || data.items || []).slice(0, 5);
  const slot = template.slots.matrix;
  const colors = ctx.colors;
  const columns = template.columns || [
    { key: "risk", label: "Risk", width: 0.32 },
    { key: "impact", label: "Impact", width: 0.23 },
    { key: "control", label: "Control", width: 0.45 }
  ];
  const headerH = 0.42;
  const rowH = (slot.h - headerH) / Math.max(rows.length, 1);
  let x = slot.x;

  addShape(slide, "roundRect", slot, {
    fill: "FFFFFF",
    line: "E5E7EB",
    radius: 0.12
  });
  columns.forEach((col) => {
    const w = slot.w * col.width;
    addShape(slide, "rect", { x, y: slot.y, w, h: headerH }, {
      fill: colors.deepRed,
      line: colors.deepRed
    });
    addText(slide, col.label, { x: x + 0.08, y: slot.y + 0.08, w: w - 0.16, h: headerH - 0.1 }, {
      fontSize: 9,
      bold: true,
      color: colors.white,
      fit: "shrink"
    }, ctx);
    x += w;
  });

  rows.forEach((row, rowIndex) => {
    let colX = slot.x;
    const y = slot.y + headerH + rowIndex * rowH;
    columns.forEach((col, colIndex) => {
      const w = slot.w * col.width;
      const fill = rowIndex % 2 === 0 ? "FBFAF7" : "FFFFFF";
      addShape(slide, "rect", { x: colX, y, w, h: rowH }, {
        fill,
        line: "E5E0D6"
      });
      addText(slide, row[col.key] || "", { x: colX + 0.1, y: y + 0.08, w: w - 0.2, h: rowH - 0.14 }, {
        fontSize: colIndex === 0 ? 10 : 8.5,
        bold: colIndex === 0,
        color: colors.ink,
        fit: "shrink",
        breakLine: false
      }, ctx);
      colX += w;
    });
  });
}

function renderLifecycleProcess(slide, template, data, ctx) {
  const steps = (data.steps || data.items || []).slice(0, 5);
  const colors = ctx.colors;
  steps.forEach((step, index) => {
    const slot = template.slots[`step_${index + 1}`];
    addShape(slide, "roundRect", slot, {
      fill: index % 2 === 0 ? colors.cream : colors.soft,
      line: "E0D7C8",
      radius: 0.14
    });
    addText(slide, String(index + 1).padStart(2, "0"), { x: slot.x + 0.18, y: slot.y + 0.18, w: 0.35, h: 0.22 }, {
      fontSize: 10,
      bold: true,
      color: colors.gold
    }, ctx);
    addText(slide, step.title || "", { x: slot.x + 0.55, y: slot.y + 0.17, w: slot.w - 0.72, h: 0.34 }, {
      fontSize: 12,
      bold: true,
      color: colors.ink,
      fit: "shrink"
    }, ctx);
    addText(slide, step.body || "", { x: slot.x + 0.22, y: slot.y + 0.68, w: slot.w - 0.44, h: 0.55 }, {
      fontSize: 8.5,
      color: colors.muted,
      fit: "shrink"
    }, ctx);
    if (index < steps.length - 1) {
      addLine(slide, { x: slot.x + slot.w + 0.08, y: slot.y + slot.h / 2, w: 0.28, h: 0 }, colors.gold, 1.2, "triangle");
    }
  });
}

function renderGovernanceLayers(slide, template, data, ctx) {
  const layers = (data.layers || data.items || []).slice(0, 5);
  const colors = ctx.colors;
  layers.forEach((layer, index) => {
    const slot = template.slots[`layer_${index + 1}`];
    const fill = [colors.deepRed, colors.gray, colors.gold, colors.cream, colors.soft][index] || colors.soft;
    const textColor = index < 3 ? colors.white : colors.ink;
    addShape(slide, "roundRect", slot, {
      fill,
      line: index < 3 ? fill : "E0D7C8",
      radius: 0.12
    });
    addText(slide, layer.title || "", { x: slot.x + 0.22, y: slot.y + 0.14, w: 2.2, h: 0.32 }, {
      fontSize: 12,
      bold: true,
      color: textColor,
      fit: "shrink"
    }, ctx);
    addText(slide, layer.body || "", { x: slot.x + 2.55, y: slot.y + 0.15, w: slot.w - 2.85, h: 0.32 }, {
      fontSize: 9,
      color: textColor,
      fit: "shrink"
    }, ctx);
  });
}

function addRiskCard(slide, slot, item, tone, ctx) {
  const colors = ctx.colors;
  const fill = colors[tone] || colors.soft;
  const dark = tone === "red" || tone === "deepRed" || tone === "gray";
  addShape(slide, "roundRect", slot, {
    fill,
    line: dark ? fill : "DED8CE",
    radius: 0.12
  });
  addText(slide, String(item.number ?? "").padStart(2, "0"), { x: slot.x + 0.16, y: slot.y + 0.2, w: 0.38, h: 0.22 }, {
    fontSize: 10,
    bold: true,
    color: dark ? colors.sand : colors.gold,
    fit: "shrink"
  }, ctx);
  addText(slide, item.title || "", { x: slot.x + 0.58, y: slot.y + 0.18, w: slot.w - 0.78, h: 0.28 }, {
    fontSize: 11,
    bold: true,
    color: dark ? colors.white : colors.ink,
    fit: "shrink"
  }, ctx);
  addText(slide, item.body || "", { x: slot.x + 0.58, y: slot.y + 0.5, w: slot.w - 0.78, h: slot.h - 0.58 }, {
    fontSize: 7.5,
    color: dark ? "F3F4F6" : colors.muted,
    fit: "shrink"
  }, ctx);
}

function addText(slide, text, box, opts, ctx) {
  if (!box || text === undefined || text === null || text === "") return;
  slide.addText(String(text), {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    fontFace: ctx.fontFace,
    fontSize: opts.fontSize || 10,
    color: opts.color || ctx.colors.ink || "111111",
    bold: Boolean(opts.bold),
    align: opts.align || "left",
    valign: opts.valign || "top",
    margin: opts.margin ?? 0.03,
    breakLine: opts.breakLine ?? false,
    fit: opts.fit || "shrink"
  });
}

function addShape(slide, kind, box, opts = {}) {
  if (!box) return;
  const shape = shapeType(slide, kind);
  slide.addShape(shape, {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    rectRadius: opts.radius,
    fill: opts.fill ? { color: opts.fill, transparency: opts.transparency || 0 } : undefined,
    line: opts.line === false ? { transparency: 100 } : { color: opts.line || "D9D4CA", width: opts.lineWidth || 0.8 }
  });
}

function addLine(slide, box, color, width = 1, endArrowType) {
  const line = { color, width };
  if (endArrowType) line.endArrowType = endArrowType;
  slide.addShape(shapeType(slide, "line"), {
    x: box.x,
    y: box.y,
    w: box.w,
    h: box.h,
    line
  });
}

function addLineBetweenSlots(slide, from, to, color, width) {
  const a = center(from);
  const b = center(to);
  addLine(slide, { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y }, color, width);
}

function shapeType(slide, kind) {
  const pptxTypes = SHAPE_TYPES;
  if (kind === "roundRect") return pptxTypes.roundRect || pptxTypes.rect || "roundRect";
  if (kind === "hexagon") return pptxTypes.hexagon || pptxTypes.rect || "hexagon";
  if (kind === "line") return pptxTypes.line || "line";
  return pptxTypes.rect || "rect";
}

function inset(box, dx, dy) {
  return {
    x: box.x + dx,
    y: box.y + dy,
    w: Math.max(0.05, box.w - dx * 2),
    h: Math.max(0.05, box.h - dy * 2)
  };
}

function center(box) {
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

function joinText(title, body) {
  return body ? `${title}\n${body}` : String(title || "");
}

function axisText() {
  return {
    fontSize: 13,
    bold: true,
    color: "111111",
    align: "center",
    fit: "shrink"
  };
}
