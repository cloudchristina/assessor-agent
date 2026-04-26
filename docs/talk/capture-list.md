# What to capture — visuals for the talk

The new Mantel-themed deck (`slides.md`) leans on **diagrams** more than screenshots. Three asset categories:

1. **Mantel brand assets** — already extracted from `Mantel … Template.pptx` into `assets/mantel/`. ✓
2. **Diagrams** — three illustrations to draw in Excalidraw / draw.io. **You make these.**
3. **Live-demo backups** — screenshots + GIFs from a real pipeline run. Capture **at least 90 minutes before the talk**.

All paths are relative to `docs/talk/`.

---

## ✓ Already captured — Mantel brand (extracted from pptx)

| File | Purpose | Used on |
|---|---|---|
| `assets/mantel/image1.png` | Mountain logo (transparent bg, no wordmark) | Every slide via `.mantel-mark` CSS — composited next to white "Mantel" text |
| `assets/mantel/image8.png` | Full color logo + dark-navy wordmark | If you ever need the dark-on-light version (e.g. for a printed handout) |
| All other `image*.png` | Best-Workplaces badges, Azure / Databricks / Snowflake partner logos | Not needed for this deck — kept for completeness |

---

## To draw — three diagrams (the deck depends on these)

| # | Diagram | File | What it must show | Tool suggestion |
|---|---|---|---|---|
| D1 | Control map | `assets/diagrams/control-map.png` | A fan/tree: APRA CPS 234 §35 at the root → 8 ISM controls in the middle column → R1–R6 on the right. Lines connecting controls to rules. Mantel-palette: navy bg, white text, light-blue lines, coral-pink for the R-nodes. | Excalidraw — set background to `#062338`, export at 1920×1080 |
| D2 | Stage I architecture | `assets/diagrams/stage1-architecture.png` | Left-to-right flow: **EventBridge → extract-uar → S3 raw/ → validate-and-hash → rules-engine → DDB findings → AppSync → dashboard.** Annotate manifest SHA-256 between extract-uar and validate-and-hash. **No agent box anywhere** — Stage I is deterministic only. | Excalidraw or draw.io. Use AWS service icons. |
| D3 | Full architecture (Stage I + Stage II) | `assets/diagrams/full-architecture.png` | Spec § 1.1 rendered cleanly. Add the agent-narrator + 3 gate Lambdas + Haiku judge + monthly PDF branch. Highlight the 4 read-only tools as small icons under the agent box. | Excalidraw / draw.io · 1920×1080 · Mantel-palette |

> **Tip:** export with transparent background so the slide's navy gradient shows through, OR fill with `#062338` to match. The deck uses `<img class="full">` so they'll fit the column.

---

## To capture — live demo backups

These are GIF/PNG fallbacks for `runbook.md § 6` (demo-failure recovery).

| # | Asset | File | How |
|---|---|---|---|
| C1 | Step Functions execution graph (all-green) | `assets/captures/sfn-weekly-execution.png` | SFN console → recent successful execution → graph view. Capture full graph (~10 states), all green. |
| C2 | **Weekly run E2E — full execution GIF** | `assets/captures/weekly-run-fallback.gif` | Screen-record (CMD+SHIFT+5 / Kap / Cleanshot @ 8fps) the SFN graph filling left-to-right during a real run. ~60s. |
| C3 | X-Ray service map | `assets/captures/xray-service-map.png` | X-Ray console → service map → filter to one trace ID. Captures the node-and-edge graph showing every Lambda. |
| C4 | **X-Ray trace map — agent tool spans** ⭐ | `assets/captures/xray-tool-spans.png` | X-Ray trace timeline → expand `agent-narrator` → show 4 `tool.*` child spans + Bedrock subsegment with token-count attrs. **This is the visual evidence for the OTel tree on slide 11.** |
| C5 | DynamoDB findings table | `assets/captures/ddb-findings-table.png` | DDB console → `findings` → query by latest demo run_id → ~7 rows visible (rule_id, severity, principal columns). |
| C6 | S3 PDF — Object Lock properties ⭐ | `assets/captures/s3-pdf-objectlock.png` | S3 console → `reports/2026-04/attestation_*.pdf` → Properties tab → Object Lock card showing **Mode: Governance · Retain Until: 2033-04-…**. |
| C7 | PDF cover page | `assets/captures/pdf-cover-page.png` | Open the rendered PDF in Preview → screenshot page 1 (run_id, trace_id, SHA-256 visible). |
| C8 | **Prompt-injection fail GIF** ⭐⭐⭐ | `assets/captures/injection-fallback.gif` | Screen-record SFN during the injection run: rules-engine green → agent-narrator green → **citation-gate RED** → quick-cut to dashboard QUARANTINED banner. ~30s. |
| C9 | Dashboard QUARANTINED banner ⭐⭐⭐ | `assets/captures/dashboard-quarantine-banner.png` | Dashboard after injection run completes → screenshot the QUARANTINED banner with the run card below. |
| C10 | Citation-gate fail JSON | `assets/captures/citation-gate-fail-json.png` | SFN injection execution → click citation-gate state → Input/Output tab → screenshot JSON `{"gate":"citation","passed":false,…}`. |

---

## Optional — Q&A safety net

| # | Asset | File | When useful |
|---|---|---|---|
| Q1 | Bedrock invocation log entry | `assets/captures/bedrock-invocation-log.png` | "How do you audit model output?" — show input/output token counts + guardrail evaluation. |
| Q2 | Cost Explorer (last 30d) | `assets/captures/cost-explorer-30d.png` | If anyone challenges the "$5/month" number. |
| Q3 | One golden-eval test result | `assets/captures/eval-golden-result.png` | "Tell me about Layer 4 evals." |
| Q4 | Pydantic ValidationError trace | `assets/captures/pydantic-validation-error.png` | "What happens with bad extractor input?" |

---

## Capture checklist — pre-flight, single page

**Diagrams (D1–D3) must be done before the rehearsal run** — slides reference them.

- [ ] D1 — `assets/diagrams/control-map.png`
- [ ] D2 — `assets/diagrams/stage1-architecture.png`
- [ ] D3 — `assets/diagrams/full-architecture.png`

**Captures (C1–C10) — done at T-90 min before the talk:**

- [ ] C1 — `sfn-weekly-execution.png`
- [ ] C2 — `weekly-run-fallback.gif`
- [ ] C3 — `xray-service-map.png`
- [ ] C4 — `xray-tool-spans.png` ⭐
- [ ] C5 — `ddb-findings-table.png`
- [ ] C6 — `s3-pdf-objectlock.png` ⭐
- [ ] C7 — `pdf-cover-page.png`
- [ ] C8 — `injection-fallback.gif` ⭐⭐⭐ **critical — never skip**
- [ ] C9 — `dashboard-quarantine-banner.png` ⭐⭐⭐
- [ ] C10 — `citation-gate-fail-json.png`

Optional:
- [ ] Q1–Q4 — Q&A safety-net assets

---

## Rendering the deck

```bash
# live preview (auto-reload as you edit)
npx -y --package=@marp-team/marp-cli@latest -- marp docs/talk/slides.md -w -s docs/talk/

# one-shot HTML build
npx -y --package=@marp-team/marp-cli@latest -- marp docs/talk/slides.md -o docs/talk/slides.html --html

# PDF (presenter backup)
npx -y --package=@marp-team/marp-cli@latest -- marp docs/talk/slides.md --pdf -o docs/talk/slides.pdf --html --allow-local-files

# PPTX (if a co-presenter needs Keynote/PowerPoint)
npx -y --package=@marp-team/marp-cli@latest -- marp docs/talk/slides.md --pptx -o docs/talk/slides.pptx --html --allow-local-files
```

`--allow-local-files` is required for PDF/PPTX so Marp can inline the Mantel logo PNGs.

The HTML build supports presenter mode (press `P`) — shows speaker notes + next-slide preview + timer.
