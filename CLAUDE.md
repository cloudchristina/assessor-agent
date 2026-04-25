# Claude Code instructions — `assessor-agent`

A Claude Code agent should read this file before doing anything else in this repo. It is the project-level navigation aid; user-specific preferences live in `~/.claude/projects/-Users-xc-Desktop-assessor-agent/memory/`.

## What this is

Australian banking / financial-services compliance agent for User Access Review (UAR). Pulls SQL Server logins + roles + permissions, runs six deterministic compliance rules mapped to ISM controls and APRA CPS 234, has a Strands agent narrate findings, gates the narrative with five hallucination defences, persists to DynamoDB, and (monthly) emits a signed-immutable PDF attestation.

Built for a 25-min serverless meetup demo; production-scope features deliberately deferred.

## Where to read what

| Thing | Path |
|---|---|
| Architectural spec | `docs/superpowers/specs/2026-04-25-irap-uar-agent-design.md` |
| Plan 1 (deployed) | `docs/superpowers/plans/2026-04-25-plan1-backend-pipeline.md` |
| User preferences + project decisions | `~/.claude/projects/-Users-xc-Desktop-assessor-agent/memory/MEMORY.md` |
| Repo source | `src/<lambda_name>/` — one Lambda per directory |
| Tests | `tests/unit/` (pytest, moto-mocked); `tests/integration/` (sandbox AWS) |
| Infrastructure | `infra/terraform/` (modules + main.tf composition) |

## Local environment — non-negotiable

- **Python interpreter:** `/Users/xc/Desktop/assessor-agent/.venv/bin/python`. The system `/opt/anaconda3/bin/python` does NOT have `strands`, `aws-lambda-powertools`, or `moto`. Using the wrong one wastes time.
- **Never** `pip install` outside the venv.
- **Tests:** `.venv/bin/python -m pytest tests/unit -q` (~90s, 92 tests at last count, 66% coverage)
- **Lint + format:** `make lint` (ruff)
- **Type check:** `make type` (pyright strict)
- **Pre-commit hooks** are configured (`.pre-commit-config.yaml`); install via `make install`.

## Deployed AWS state

- Region: `ap-southeast-2`
- Pipeline currently deployed and successfully running. Last verified weekly run: 75s end-to-end, 7 findings (R1, R2, R4, R5, R6×3), judge faithfulness 1.0.
- State machine ARN: `cd infra/terraform && terraform output -raw state_machine_arn`
- Trigger a run:
  ```bash
  aws stepfunctions start-execution \
    --state-machine-arn $(terraform output -raw state_machine_arn) \
    --input '{"cadence":"weekly","started_at":"<ISO8601>"}' \
    --region ap-southeast-2
  ```
- View traces: Step Functions console → execution → "X-Ray trace map" link → click `agent-narrator` segment → see tool-call child spans + Bedrock subsegment with token counts
- Run extractor in synthetic-data mode: set `SYNTHETIC_DATA_S3_URI` Lambda env var to an S3 CSV URI; extractor skips pymssql.

## Architecture (one paragraph)

EventBridge Scheduler fires Step Functions on weekly + monthly crons → SFN runs ten Python Lambdas in sequence: `extract-uar` (or synthetic CSV) → `validate-and-hash` → `rules-engine` (six R1–R6 rules, deterministic) → `agent-narrator` (Strands + Bedrock Sonnet, calls four read-only tools, produces structured `NarrativeReport`) → three gates in parallel (`citation-gate`, `reconciliation-gate`, `entity-grounding-gate`) → `judge` (Bedrock Haiku faithfulness score) → `publish-triage` (writes to DDB) → `generate-pdf` (monthly only, Object Lock 7y). Strands native OTel → ADOT layer → X-Ray.

## Project conventions

- **Pydantic v2 at every I/O boundary.** Models live in `src/shared/models.py`.
- **Structured JSON logs** via `aws-lambda-powertools` (`src/shared/logging.py`); always include `correlation_id=run_id`.
- **One Lambda = one `src/` package = one `tests/unit/test_*.py`** file. Resist the urge to combine.
- **Rules:** one file per rule in `src/rules_engine/rules/`, registered in the `RULES` list in `__init__.py`. Each rule has a per-rule unit test with hand-written cases.
- **Terraform modules** under `infra/terraform/modules/` are reused via the composition in `main.tf`. Adding a Lambda = add a module call, not a new module.
- **Commit style:** `<type>(<scope>): <imperative>` (e.g. `fix(agent): restore tool-calling`). Co-author trailer for Claude commits.

## Known gotchas (read before debugging)

- **Strands `Agent.structured_output()` is deprecated.** Use `agent(prompt, structured_output_model=Model)` and read `result.structured_output`. The old method bypasses the tool-use event loop, which removes tool-call OTel spans and weakens the agent boundary. Fixed in PR #1 (`bffb1c8`).
- **DynamoDB rejects raw Python floats.** Wrap put-item payloads with `json.loads(json.dumps(item), parse_float=Decimal)` (see `publish_triage/handler.py`).
- **Lists vs SetSet.** `databases` and `ism_controls` use DDB `L` (List of String), not `SS`. DDB rejects empty SS, and Pydantic emits `list[str]`.
- **moto strictness.** Use bucket name like `test-bucket-123`, not `b` — moto 5.x rejects short names.
- **`tests/conftest.py` sets dummy AWS creds** so moto can intercept Lambdas that build boto3 clients at module-import time.
- **`tfsec` is not installed locally.** `tflint` + `terraform validate` are the local gates; tfsec runs in CI only.
- **Python 3.13** — Lambda runtime + local. Some Strands type hints assume 3.10+.
- **Bedrock model ID** comes from env var `BEDROCK_MODEL_ID` (default `anthropic.claude-sonnet-4-6`). The deployed slide screenshot showed Sonnet 4.5 — confirm the actual env var matches the slide on stage.
- **`LAST_ACTIVE_SQL` in extractor uses `sys.dm_exec_sessions`** which only returns currently-connected sessions, not historical login events — known compliance correctness bug for R2 (dormant admin). Fix in production = SQL Server Audit to S3. For demo, synthetic data sidesteps it.

## When working on this project

1. **Read the spec.** It is the source of truth for what the system should do.
2. **Read the plan.** It tells you what has been built and what conventions were adopted.
3. **Check `MEMORY.md`** for user preferences — especially the "scope aggressively for demo" feedback. Do not over-engineer; do not trim what the spec already approved.
4. **TDD when fixing bugs.** Write the failing test first; the test proves the bug is real.
5. **Use `superpowers:systematic-debugging`** or `engineering:debug` for non-obvious failures. Random fixes waste time.
6. **Commit per task.** Frequent, small, descriptive commits beat batched mega-commits.
7. **Push to feature branches**, open PRs (or push to main for docs/configuration). Solo dev workflow but PRs leave good history.

## In-flight work

- **Plan 2 (eval suite)** — brainstorm in progress. Scope: full 5-layer eval per spec Section 5. Status: paused at architecture confirmation; needs design doc.
- **Plan 3 (frontend dashboard)** — Amplify React + Cognito + AppSync + DDB. Not started.
- **Plan 4 (realistic test data + tracing observation)** — synthetic-data generator with abnormal-activity scenarios + demo runbook. Not started.
- **Open question:** verify the deployed PR #1 fix actually shows tool-call spans in X-Ray on the next live run.
