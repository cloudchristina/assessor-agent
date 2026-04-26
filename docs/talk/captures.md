# What to capture — screenshots & GIFs for the talk

Capture all of these **at least 90 minutes before the talk**, save under `docs/talk/assets/captures/`, and reference them from the deck and the demo-failure recovery script in `runbook.md` § 6.

Two reasons each asset matters:
1. **Live backup** — if a demo fails, you fall back to the GIF and keep narrating.
2. **Visual aid** — the slides reference these PNGs as `bg right:55% fit` so audience sees the artefact while you talk.

---

## Required — the live demo backups (Demo 1 → Demo 4)

| # | Asset | File | Source | Caught when… |
|---|---|---|---|---|
| 1 | Step Functions execution graph (all-green) | `assets/captures/sfn-weekly-execution.png` | Step Functions console → executions → recent successful run → graph view. Capture full graph (10 states), all green. | Runbook § 3.1 step 2; deck slide 7 visual aid |
| 2 | **Step Functions weekly run — full execution GIF** | `assets/captures/weekly-run-fallback.gif` | Screen-record (CMD+SHIFT+5) the SFN graph filling left-to-right during a real run. ~60s. Use Kap or Cleanshot at 8 fps. | Runbook § 6 — fallback if Wi-Fi drops |
| 3 | X-Ray service map (one trace per run) | `assets/captures/xray-service-map.png` | X-Ray console → service map → filter to one execution's trace ID. Capture the node-and-edge graph showing all Lambdas. | Backup slide A; runbook § 3.1 step 3 |
| 4 | X-Ray trace map — agent-narrator drilldown showing tool spans | `assets/captures/xray-tool-spans.png` | X-Ray trace timeline → expand `agent-narrator` segment → show 4 `tool.*` child spans + Bedrock subsegment with token counts in attribute panel. | ⭐ Money Moment 2; runbook § 3.2 |
| 5 | DynamoDB findings table — latest run rows | `assets/captures/ddb-findings-table.png` | DynamoDB console → `findings` table → query by `run_id` of latest demo run → show ~7 rows with rule_id, severity, principal columns visible. | Runbook § 6 — fallback for stale dashboard |
| 6 | S3 PDF object — Object Lock properties panel | `assets/captures/s3-pdf-objectlock.png` | S3 console → `reports/2026-04/attestation_*.pdf` → Properties tab → screenshot the Object Lock card showing **Mode: Governance · Retain Until: 2033-04-…**. | ⭐ Money Moment 4; runbook § 3.4 step 3 |
| 7 | The PDF cover page itself | `assets/captures/pdf-cover-page.png` | Open the rendered PDF in Preview → screenshot page 1 (run_id, trace_id, SHA-256 visible). | Runbook § 3.4 step 4; backup slide C |
| 8 | **Prompt-injection fail GIF** | `assets/captures/injection-fallback.gif` | Screen-record the SFN graph during the injection run: rules-engine green → agent-narrator green → citation-gate **RED**. Then quick-cut to dashboard QUARANTINED banner. ~30s. | Runbook § 6 — **critical**, do not skip |
| 9 | Quarantine banner on dashboard | `assets/captures/dashboard-quarantine-banner.png` | Dashboard → after the injection run completes → screenshot the QUARANTINED banner with the run card below. | ⭐⭐⭐ Money Moment 3; runbook § 3.3 step 5 |
| 10 | Citation-gate Lambda I/O JSON | `assets/captures/citation-gate-fail-json.png` | SFN console → injection execution → click citation-gate state → Input/Output tab → screenshot the JSON `{"gate":"citation","passed":false,…}`. | Runbook § 3.3 step 4 |

---

## Required — the slide visual assets (referenced by name in `slides.md`)

| # | Asset | File | Source |
|---|---|---|---|
| 11 | Architecture diagram (clean version of spec § 1.1 ASCII) | `assets/architecture-diagram.png` | Render in draw.io or Excalidraw. Match the spec § 1.1 layout. Export 1920×1080 PNG, transparent background. **Must show**: EventBridge → SFN → 6 Lambdas → DDB + S3, with the agent box clearly *not* central. |
| 12 | "UAR is manual" collage | `assets/uar-screenshot-collage.png` | Mock — composite of (a) an 8-tab Excel screenshot showing column-soup, (b) a Jira board with ~200 tickets, (c) a redacted email thread. **Use synthetic / mock data only.** Tools: Figma, Cleanshot collage. |

---

## Optional — Q&A safety net

| # | Asset | File | Why |
|---|---|---|---|
| 13 | Bedrock invocation log sample | `assets/captures/bedrock-invocation-log.png` | If asked "how do you audit model output?" — show one log entry with input/output token counts and guardrail evaluation result. |
| 14 | Cost Explorer screenshot (last 30d) | `assets/captures/cost-explorer-30d.png` | If anyone challenges the "$5/month" number — show the actual graph. |
| 15 | One golden-eval test result | `assets/captures/eval-golden-result.png` | If asked about Layer 4 (CI evals) — show one test case from `evals/golden/` with pass/fail and metric scores. |
| 16 | Pydantic validation error from a manual bad-input test | `assets/captures/pydantic-validation-error.png` | If asked "what happens with bad input from extractor?" — show a clean ValidationError trace from a manual run. |

---

## Capture checklist (single-page, pre-flight)

Tick the asset off as it lands in `docs/talk/assets/captures/`:

- [ ] 1 — `sfn-weekly-execution.png`
- [ ] 2 — `weekly-run-fallback.gif`
- [ ] 3 — `xray-service-map.png`
- [ ] 4 — `xray-tool-spans.png` ⭐
- [ ] 5 — `ddb-findings-table.png`
- [ ] 6 — `s3-pdf-objectlock.png` ⭐
- [ ] 7 — `pdf-cover-page.png`
- [ ] 8 — `injection-fallback.gif` ⭐⭐⭐ **critical**
- [ ] 9 — `dashboard-quarantine-banner.png` ⭐⭐⭐
- [ ] 10 — `citation-gate-fail-json.png`
- [ ] 11 — `architecture-diagram.png`
- [ ] 12 — `uar-screenshot-collage.png`

Optional:
- [ ] 13–16 — Q&A assets

---

## Rendering the deck

```bash
# preview live
npx @marp-team/marp-cli docs/talk/slides.md --preview

# export to HTML (for browser presenter mode)
npx @marp-team/marp-cli docs/talk/slides.md -o docs/talk/slides.html

# export to PDF (for backup)
npx @marp-team/marp-cli docs/talk/slides.md --pdf -o docs/talk/slides.pdf

# export to PPTX (if a co-presenter needs to edit)
npx @marp-team/marp-cli docs/talk/slides.md --pptx -o docs/talk/slides.pptx
```

Marp picks up the assets via relative paths, so as long as they live under `docs/talk/assets/`, the export bundles them.
