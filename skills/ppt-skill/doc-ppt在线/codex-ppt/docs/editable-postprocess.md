# Editable Postprocess

Read this only when the user explicitly asks for an editable PPTX, asks to
make the generated deck editable, or the agreed deliverable includes an
editable tail route after the normal image-based deck is assembled.

## Boundary

The normal `codex-ppt` workflow remains responsible for source understanding,
outline approval, visual style, image backend selection, slide image generation,
QA, speaker notes, and the image-based PPTX.

Editable output is a tail step. Start it only after the image-based PPTX and the
final `origin_image/slide_XX.png` files exist. At that point choose exactly one
route:

- Route A, `image_to_editable_ppt`: visual reconstruction priority. It consumes
  the final full-slide PNGs, uses OCR/text hints and page reconstruction, and
  produces object-level editable pages. Use this when preserving the final PNG
  look is more important than authoring from the source text.
- Route B, `native editable rebuild`: text stability priority. It uses the final
  PNGs as visual/style references, but rebuilds slide content from the approved
  outline, source text, tables, speaker notes, and a page manifest into native
  PPT objects. Use PptxGenJS as the default native runtime in Codex tests and
  offline deployments unless the user explicitly selects another native PPTX
  runtime. Use this for Chinese reports, papers, policy decks, and other
  text-heavy decks where editable text fidelity is more important than exact
  pixel reconstruction.

Do not mix slide-generation state with editable-reconstruction state:

- `slide_jobs.json` and `slide_run_state.json` belong to `codex-ppt`.
- `editable_run/page_jobs.json` and page manifests belong to the embedded
  `editable` module used by Route A.
- Route B must use its own native rebuild directory under the project directory,
  such as `native_editable_run/`, and must not alter slide-generation state.
- Slide workers generate full-slide images. Page workers reconstruct editable
  objects from already-generated page images in Route A.

## Route Selection

If the user has already chosen a route, follow it. If they only asked for an
editable PPTX and did not choose a route, default to Route A after the
image-based deck is complete. Briefly tell the user that Route A is being used
because visual reconstruction of the approved PNG pages is the default, and
mention that Route B remains available if they explicitly prefer source-text
native rebuilding.

```text
默认尾部路线：A. 视觉还原优先：整页 PNG -> OCR/text hints -> image_to_editable_ppt 重建
可选路线：B. 文本稳定优先：参考最终 PNG 风格，用原文内容 + manifest + 原生 PPT 对象重建
```

Recommend Route A when:

- The user approved final PNG pages and wants the editable deck to visually
  match those pages as closely as possible.
- The source is screenshots, scanned pages, an image-based PPT/PDF, or a deck
  whose visual identity is the primary deliverable.
- The existing embedded `editable/` workflow and OCR/text hints are available.

Use Route B only when the user explicitly chooses it or clearly prioritizes
native source-text rebuilding over visual reconstruction. Route B is suitable
when:

- The source is `.docx`, Markdown, plain text, or a PDF with reliable text.
- The deck is Chinese-heavy, table-heavy, or policy/research/report-oriented.
- The user cares more about editable text accuracy, future editing, and stable
  text boxes than exact pixel reconstruction.
- PptxGenJS or an explicitly approved native PPTX authoring runtime is available
  in the deployment environment.

If the chosen route cannot run because a required runtime is unavailable, report
that route as blocked and ask whether to switch to the other route. Do not fake
editability by overlaying editable text on top of full-slide source rasters.

## Route A: Image To Editable PPT

After the normal assembly succeeds and the final `origin_image/slide_XX.png`
files are present, run:

```bash
python {skill_root}/scripts/rebuild_editable_ppt.py {project_dir}
```

`{project_dir}` is the deck directory that contains `origin_image/`. The script
sorts `slide_*.png`, creates `{project_dir}/editable_run`, and calls the embedded
`editppt prepare` command from `editable/cli`.

Useful options:

```bash
python {skill_root}/scripts/rebuild_editable_ppt.py {project_dir} \
  --job-dir {project_dir}/editable_run \
  --max-concurrent-pages 6
```

Use `--no-text-hints` only for confidential/local-only runs or when OCR setup is
known to be unavailable and the user accepts lower text fidelity.

## Continue With The Embedded Module

After prepare, follow the embedded module contract at:

```text
editable/SKILL.md
editable/references/cli-helper.md
editable/references/manifest-schema.md
editable/references/page-decision-tree.md
editable/prompts/page-worker.md
```

Use `editable/` as the embedded module root wherever those files say
`<skill-root>`.

Drive the run through:

```bash
python {skill_root}/editable/cli/editppt/cli.py run next {project_dir}/editable_run --json
```

For multi-page decks, dispatch page workers as the embedded module requires. If
the current runtime cannot spawn page workers, stop and report that editable
reconstruction is blocked after prepare. Do not rebuild a multi-page deck
sequentially in the parent agent.

For a single-page run, the parent agent may follow the embedded module's local
page-reconstructor mode after `editppt run dispatch --local` records the claim.

## Final Output

When all pages are recorded, run:

```bash
python {skill_root}/editable/cli/editppt/cli.py run finalize {project_dir}/editable_run
```

The editable final PPTX is written under:

```text
{project_dir}/editable_run/final/
```

Report both deliverables:

- the original image-based PPTX from `codex-ppt`
- the editable PPTX from `editable_run/final/`

Also report the editable run validation result and any page-level warnings or
blockers.

## Route B: Native Editable Rebuild

Route B is a separate tail route. It does not consume `editable/` page jobs and
does not OCR the final PNGs as the source of truth. Instead, use the final PNGs
as visual references and rebuild native PPT objects from source content.

### Default Runtime: PptxGenJS

Use PptxGenJS as the default Route B runtime when testing this skill in Codex
and when deploying offline, unless the user explicitly chooses another native
PPTX runtime.

Route B dependencies:

- Node.js runtime.
- `pptxgenjs` Node package, installed in the active project/runtime or vendored
  for offline deployment.
- A PPTX preview/render path for QA, such as LibreOffice headless, PowerPoint,
  WPS, or another approved renderer available in the deployment environment.
- The source parser used by the main workflow, such as `python-docx` for `.docx`
  inputs, remains the text authority.

Before starting Route B, check that PptxGenJS is available to the Node runtime
that will build the deck:

```bash
node -e "require.resolve('pptxgenjs')"
```

If this check fails, report Route B as blocked by the missing PptxGenJS runtime
and ask whether to install/provide it or switch to Route A. Do not silently fall
back to `python-pptx`, HTML screenshots, full-slide raster overlays, or the
embedded Route A `editable/` module.

For offline deployment, package `node`, `pptxgenjs`, and its transitive
dependencies with the skill runtime or install them from a local package cache
before running Route B. Do not require live npm access during a deck build.

### Bundled Dynamic Native Builder

Route B includes an artifact-tool-like dynamic native builder rewritten for
PptxGenJS. It does not depend on `@oai/artifact-tool`. Use this as the preferred
Route B path when the slide can be expressed as a structured layout plan.

The model should output slide structure, not raw coordinates:

- `layout_type`: one of `auto_hub_spoke`, `auto_cards`, `auto_process`,
  `auto_matrix`, `auto_layers`, or `auto_two_column`.
- source-backed text fields: `title`, `subtitle`, `items`, `steps`, `rows`,
  `layers`, `center`, `takeaway`, and `notes`.
- `connector_policy`: use `none` by default; use `minimal` only when connectors
  clarify a simple relationship map.

The dynamic builder computes object coordinates, card grids, radial placement,
step widths, layer widths, table rows, font shrinking, and connector endpoints.
Do not ask the model to hand-author precise `x/y/w/h` coordinates for these
supported layout types.

Preferred build command:

```bash
node {skill_root}/scripts/build_native_pptx_dynamic.mjs \
  --manifest {project_dir}/native_editable_run/manifest.json \
  --out {project_dir}/native_editable_run/{deck_name}-native-editable.pptx
```

Bundled dynamic files:

- `scripts/build_native_pptx_dynamic.mjs`: preferred Route B PptxGenJS builder.
- `native_templates/dynamic_example_manifest.json`: minimal dynamic manifest for
  testing.
- `native_templates/schema.json`: accepts both dynamic `layout_type` plans and
  fixed `template_id` fallback manifests.

### Bundled Fixed Template Fallback

Route B also includes a small deterministic template library derived from the
approved native-object sample style and rewritten for PptxGenJS. Use it as a
fallback when a slide needs a known fixed layout or when the dynamic builder
does not yet support the desired structure.

Bundled files:

- `native_templates/templates.json`: fixed template ids, slots, limits, colors,
  connector policy, and fallback rules.
- `native_templates/example_manifest.json`: minimal example input for testing.
- `scripts/build_native_pptx.mjs`: PptxGenJS builder that reads the manifest and
  writes a native editable PPTX.

Seed templates:

- `six_risk_hub_spoke_clean`
- `six_cards_grid`
- `risk_control_matrix`
- `lifecycle_process`
- `governance_layers`

When using the fixed fallback, the model should choose a `template_id` and fill
the manifest content fields. Do not ask the model to invent fresh object
coordinates for supported templates. Add a new template to
`native_templates/templates.json` and the builder only when the dynamic builder
and existing fixed templates cannot express the slide cleanly.

Fixed fallback build command:

```bash
node {skill_root}/scripts/build_native_pptx.mjs \
  --manifest {project_dir}/native_editable_run/manifest.json \
  --out {project_dir}/native_editable_run/{deck_name}-native-editable.pptx
```

Required inputs:

- Approved `outline.md`.
- Final `origin_image/slide_XX.png` files as style/layout references.
- Source-extracted text, tables, figures, and approved slide copy.
- `speech.md` when speaker notes are expected.

Required native rebuild artifacts:

- A route-local run directory, such as `{project_dir}/native_editable_run/`.
- A per-slide manifest or equivalent structured plan that lists native text
  boxes, shapes, connectors, tables, charts, and image assets.
- A PptxGenJS build script or equivalent route-local builder source.
- Preview renders for QA.
- A final editable `.pptx`.

### Route B Layout Discipline

Route B must be planner-driven or template-driven. Do not let the model freely
place every `x/y/w/h` coordinate or connector from the visual PNG. Prefer the
dynamic native builder: choose a supported `layout_type`, fill it with
source-backed content, and let the builder calculate positions. Use fixed
templates only as fallback or for layouts that are intentionally locked.

The per-slide manifest must include:

- `layout_type` for dynamic plans or `template_id` for fixed fallback plans.
- Slide role, source-backed content fields, density/connector policy when
  needed, and speaker notes when expected.
- For fixed fallback plans, a `slots` list with fixed positions for titles,
  cards, tables, diagrams, callouts, footers, and visual assets.
- An `objects` list where every visible text object records its source text,
  object type, assigned slot, font size, wrapping rule, and fallback behavior
  when text is too long.
- A `connectors` list only when connectors clarify the diagram. Each connector
  must declare source/target object ids, source/target ports, route type, and
  avoid zones.

Prefer these constrained templates before inventing a new layout:

- `title_cover`: cover slide with native title/subtitle and optional text-free
  background artwork.
- `section_divider`: native chapter title with one or two supporting lines.
- `two_column_argument`: claim/evidence or problem/response comparison.
- `three_to_six_cards`: modular card grid for dense report findings.
- `process_flow`: numbered horizontal or vertical steps.
- `timeline`: chronological sequence with fixed tick positions.
- `matrix_quadrant`: 2x2 policy, risk, or priority matrix.
- `hub_spoke_fixed`: center node plus fixed outer slots; use only with explicit
  ports and short labels.
- `table_snapshot`: native table or simplified table cards.
- `quote_or_takeaway`: one claim plus supporting evidence blocks.

For complex framework diagrams, prefer a simpler fixed template over a visually
busy reconstruction. If a hub-spoke or relationship map creates crossed lines,
lines through text, or ambiguous reading order, switch that slide to a card
grid, quadrant, process flow, or split the content across slides.

Connector rules:

- Connectors attach to declared ports, not arbitrary center points.
- Use straight, elbow, or orthogonal routes only. Avoid diagonal connector webs
  unless the route is visually isolated from text.
- Connectors must not cross title/body text boxes, tables, or key labels.
- Use no connectors when proximity, numbering, alignment, or color grouping is
  enough to explain the relationship.
- Keep connectors behind foreground shapes but above decorative backgrounds.

Route B object rules:

- Keep all titles, body text, tables, labels, framework nodes, and ordinary
  diagrams as native editable PPT objects generated by PptxGenJS.
- Use image assets only for backgrounds, illustrations, icons, visual texture,
  cover imagery, or complex non-text visuals.
- Treat the final PNG as style and layout reference only; do not place the
  entire PNG as a full-slide background with editable text over it.
- Use source text, not OCR from the generated PNG, as the text authority.
- Use a fixed 16:9 canvas and explicit positions/sizes from the per-slide
  manifest. Avoid auto-layout choices that cannot be reproduced or QA repaired.
- If a slide cannot be rebuilt natively without unacceptable drift, report the
  slide-level blocker and ask whether to switch that slide or the whole deck to
  Route A.

Route B hard failures:

- The editable PPTX uses a full-slide raster as the main slide content, except
  for a text-free cover/background asset.
- Readable Chinese or key business text is baked into an image asset instead of
  native text objects.
- The build does not create a route-local manifest and PptxGenJS builder.
- A dense diagram is produced from unconstrained free placement rather than a
  declared dynamic layout plan or fixed template.
- Rendered preview shows text overflow, object overlap, clipped labels, lines
  crossing text, or connectors whose source/target relationship is ambiguous.
- Slide text is taken from OCR or generated PNG text instead of approved source
  content.

Route B QA:

- Render the editable PPTX to preview images.
- Check text fidelity against source content, not the generated PNG.
- Check visual similarity against the final PNGs at the level of layout,
  hierarchy, palette, and rhythm.
- Check that each slide used a declared dynamic `layout_type` or fixed
  `template_id`, and that all major objects are inside computed or assigned
  slots.
- Check connector routing against the avoid zones in the manifest.
- Fix text overflow, object overlap, clipping, incorrect wrapping, missing
  speaker notes, and invalid PPTX structure before delivery.

Route B final report:

- Report the native editable PPTX path.
- Report the native rebuild run directory and QA evidence.
- Mention any slides that used raster assets for complex visuals.
- Mention any known visual differences from the image-based deck.
