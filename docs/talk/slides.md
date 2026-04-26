---
marp: true
theme: default
size: 16:9
paginate: true
backgroundColor: "#062338"
color: "#ffffff"
style: |
  /* ---------- Mantel theme ---------- */
  section {
    background: radial-gradient(ellipse 90% 70% at 25% 50%, #14516E 0%, #0B3551 35%, #062338 100%);
    color: #ffffff;
    font-family: -apple-system, "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-weight: 400;
    font-size: 28px;
    padding: 70px 80px 80px 80px;
  }
  section h1 { color: #ffffff; font-weight: 700; font-size: 56px; line-height: 1.1; letter-spacing: -0.02em; margin: 0 0 18px 0; }
  section h2 { color: #7BB7E0; font-weight: 500; font-size: 30px; margin: 0 0 24px 0; }
  section h3 { color: #ffffff; font-weight: 600; font-size: 26px; }
  section strong { color: #ffffff; font-weight: 700; }
  section em { color: #7BB7E0; font-style: normal; font-weight: 500; }
  section a { color: #7BB7E0; text-decoration: none; border-bottom: 1px solid rgba(123,183,224,0.4); }
  section code { background: rgba(255,255,255,0.06); color: #E5777E; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }
  section pre { background: rgba(0,0,0,0.35); border: 1px solid rgba(123,183,224,0.2); border-radius: 8px; padding: 18px 24px; font-size: 22px; }
  section pre code { background: transparent; color: #D9E5EC; padding: 0; }
  section table { border-collapse: collapse; color: #ffffff; font-size: 24px; margin-top: 12px; }
  section th { color: #7BB7E0; text-align: left; font-weight: 600; border-bottom: 2px solid rgba(123,183,224,0.4); padding: 10px 14px; }
  section td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.08); }
  section blockquote { border-left: 4px solid #E5777E; color: #D9E5EC; font-style: italic; margin: 24px 0; padding-left: 18px; }
  section ul { margin: 0; padding-left: 28px; }
  section li { margin: 8px 0; }
  section::after { color: rgba(255,255,255,0.5); font-size: 16px; }   /* page number */
  /* ---------- Mantel logo (white wordmark, bottom-right of content slides) ---------- */
  .mantel-mark { position: absolute; right: 60px; bottom: 28px; display: flex; align-items: center; gap: 10px; }
  .mantel-mark img { height: 30px; width: auto; }
  .mantel-mark span { color: #ffffff; font-weight: 700; font-size: 22px; letter-spacing: -0.01em; }
  /* ---------- Title-slide variant: top-left logo, big hero ---------- */
  section.title { padding: 60px 80px; }
  section.title h1 { font-size: 76px; margin-top: 90px; }
  section.title h2 { font-size: 32px; color: #7BB7E0; margin-top: 16px; font-weight: 400; }
  section.title .tag { position: absolute; bottom: 60px; left: 80px; color: #7BB7E0; font-size: 22px; }
  section.title .mantel-mark { top: 50px; left: 80px; right: auto; bottom: auto; }
  section.title .mantel-mark img { height: 44px; }
  section.title .mantel-mark span { font-size: 30px; }
  /* ---------- Divider slide variant ---------- */
  section.divider { text-align: left; }
  section.divider h1 { font-size: 72px; margin-top: 200px; }
  section.divider h2 { font-size: 36px; color: #7BB7E0; font-weight: 400; margin-top: 24px; }
  section.divider .stagelabel { color: #E5777E; font-size: 24px; text-transform: uppercase; letter-spacing: 0.18em; font-weight: 600; }
  /* ---------- Big-number slide ---------- */
  section.bignum h1 { font-size: 200px; line-height: 1; margin-top: 60px; color: #ffffff; }
  section.bignum h2 { color: #7BB7E0; font-size: 32px; max-width: 70%; }
  section.bignum .label { color: #E5777E; text-transform: uppercase; letter-spacing: 0.18em; font-size: 22px; }
  /* ---------- Three-column layout ---------- */
  .cols-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 28px; margin-top: 30px; }
  .col-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(123,183,224,0.25); border-radius: 12px; padding: 24px; }
  .col-card .num { color: #E5777E; font-weight: 700; font-size: 22px; }
  .col-card h3 { color: #ffffff; font-size: 24px; margin: 8px 0 12px 0; }
  .col-card p { color: #D9E5EC; font-size: 20px; margin: 0; line-height: 1.4; }
  /* ---------- Two-column layout ---------- */
  .cols-2 { display: grid; grid-template-columns: 1.1fr 1fr; gap: 36px; align-items: start; }
  /* ---------- Layered stack diagram ---------- */
  .stack { display: flex; flex-direction: column; gap: 8px; margin-top: 20px; }
  .stack .layer { display: grid; grid-template-columns: 80px 1fr 1.6fr; gap: 18px; align-items: center; padding: 14px 20px; background: rgba(255,255,255,0.04); border-left: 4px solid #7BB7E0; border-radius: 6px; }
  .stack .layer .n { color: #E5777E; font-weight: 700; font-size: 22px; }
  .stack .layer .name { color: #ffffff; font-weight: 600; font-size: 22px; }
  .stack .layer .what { color: #D9E5EC; font-size: 20px; }
  /* ---------- Tree diagram for OTel spans ---------- */
  .tree { font-family: "SF Mono", "Menlo", monospace; font-size: 20px; color: #D9E5EC; line-height: 1.6; background: rgba(0,0,0,0.3); padding: 24px 28px; border-radius: 10px; border: 1px solid rgba(123,183,224,0.2); }
  .tree .span-name { color: #7BB7E0; }
  .tree .attr { color: #E5777E; }
  img.full { width: 100%; height: auto; }
---

<!--
SPEAKER NOTE — DECK USAGE
- 14 numbered slides + 2 stage dividers + 3 backups. Total ~12-min slide-time;
  ~13 min live demo (interleaved between the Stage II tools slide and the
  defence-stack slide).
- Mantel theme: dark-navy radial gradient, white headings, light-blue subtitles,
  coral-pink accents. Logo top-left on title slide, bottom-right on others.
- Image placeholders → see docs/talk/capture-list.md.
- Money moments tagged ⭐. Cut-list in docs/talk/runbook.md § 5.
-->

<!-- _class: title -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# An auditor-grade compliance agent

## Six Lambdas, one Strands agent, five gates — and a live attempt to break it

<div class="tag">Christina Chen · Solution Architect, Banking & Finance · Serverless Meetup Sydney · April 2026</div>

<!--
TIMING 0:00 → 0:30. Land slowly. Two beats. Then:
"Twenty-five minutes. We're going to build a regulator-grade compliance agent and try to break it live. Let's go."
Hit countdown timer as you say "now".
-->

---

<!-- _class: bignum -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="label">The pain</div>

# 3,000

## engineer-hours per year, per Australian bank, producing one report.
APRA CPS 234 §35 — User Access Review. Today: spreadsheets, screenshots, email threads.

<!--
TIMING 0:30 → 2:00. Hold the number. Then:
"That number is from a CISO conversation, anonymised. Last UAR cycle one bank told me about: 47 reviewers, 11 weeks, one finding missed. Auditors don't forget missed findings."
PAUSE. Move on.
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# What we have to satisfy

<div class="cols-2">

![full](./assets/diagrams/control-map.png)

<div>

**APRA CPS 234 §35** — periodic review of access · monthly attestation
&nbsp;
**ISM-1546** — MFA on privileged accounts → **R1**
**ISM-1509 / 1555** — revoke when no longer needed → **R2 · R4**
**ISM-1175** — segregation of duties → **R3**
**ISM-0445** — least privilege → **R5**
**ISM-1545** — no shared / generic accounts → **R6**

> *"Every finding cites a control. Every control cites a rule."*

</div>
</div>

<!--
TIMING 2:00 → 4:00.
Diagram (assets/diagrams/control-map.png — TODO): a fan: CPS 234 → 8 ISM controls → R1-R6.
Land: this is what makes the system audible — every finding traces back to a published Australian government control.
-->

---

<!-- _class: divider -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="stagelabel">Stage I</div>

# The deterministic foundation

## Six rules · six Lambdas · zero LLM

<!--
TIMING 4:00 → 4:30. Brief. Then onto the architecture diagram.
"The boring half. We do this first, on purpose. Once it works deterministically, then — and only then — do we let an agent near it."
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Stage I architecture

![full](./assets/diagrams/stage1-architecture.png)

<!--
TIMING 4:30 → 6:00.
Diagram (assets/diagrams/stage1-architecture.png — TODO):
  EventBridge → extract-uar → S3 raw/ → validate-and-hash → rules-engine → DDB findings + AppSync → dashboard
Walk LEFT-TO-RIGHT. Emphasise: every box is one Lambda, one responsibility, one Pydantic contract. Manifest SHA-256 = coverage proof.
Stage line: "No LLM in this picture. Pure Python. The auditor can replay any finding from raw CSV."
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Stage I challenges

<div class="cols-3">
<div class="col-card">
<div class="num">01</div>
<h3>Rules correctness</h3>
<p>Six rules → six per-rule golden suites. Counterfactual tests prove flipping one input flips only the expected rule.</p>
</div>
<div class="col-card">
<div class="num">02</div>
<h3>Provable coverage</h3>
<p>Manifest SHA-256 of sorted row-IDs. Re-derivable by the auditor. "We didn't miss a row" becomes a hash check, not a promise.</p>
</div>
<div class="col-card">
<div class="num">03</div>
<h3>Speaks auditor</h3>
<p>Every finding carries its <strong>ISM control</strong> + <strong>evidence dict</strong>. Reviewer doesn't ask "why?" — the finding answers it inline.</p>
</div>
</div>

<!--
TIMING 6:00 → 7:30.
Walk the three cards. Each one is a real engineering decision, not theatre.
The "speaks auditor" card is what most demos skip — it's the difference between a finding and an actionable finding.
-->

---

<!-- _class: bignum -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="label">Why an agent at all?</div>

# 200+

## findings per cycle. Reviewers don't read evidence dicts — they read stories.
The agent is a **read-only narrator**. It clusters, contextualises, drafts remediation. **It does not count, vote, or assign severity.**

<!--
TIMING 7:30 → 8:30.
This is the conceptual bridge from Stage I → Stage II. Without this slide, the audience asks "why not just stop after rules?"
Answer: 200 findings is a 6-hour reviewer task. With clustering + narrative, it's a 30-minute task.
-->

---

<!-- _class: divider -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="stagelabel">Stage II</div>

# The agent layer

## …but can you trust it in front of an auditor?

<!--
TIMING 8:30 → 9:00.
This is the provocation. Look at the audience. Then:
"Short answer: you can't trust the agent. You can trust the architecture around it. Let me show you."
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Why Strands?

| | **Raw Bedrock SDK** | **LangChain** | **Strands** ✓ |
|---|---|---|---|
| Tool registry | DIY | heavy abstractions | `@tool` decorator |
| Structured output | manual JSON-mode | manual parser | Pydantic via tool-use |
| OTel spans | manual instrumentation | plugins, partial | **native, every call** |
| Bedrock Guardrails | manual wiring | manual | first-class |
| Code surface | high | very high | low |

> *"Strands gives us OTel out of the box. Every tool call, every token, every judge score is a span in X-Ray. That is our compliance evidence."*

<!--
TIMING 9:00 → 10:30.
Don't bash LangChain — say "LangChain is great, just heavier than we need". The OTel-native row is THE differentiator for compliance work.
If asked: "we evaluated LangGraph and Bedrock Agents too. Strands won on observability + AWS-native + small surface area."
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Four read-only tools — every call is a signed span

<div class="cols-2">

```python
@tool
def get_finding(finding_id) -> Finding: ...

@tool
def get_ism_control(control_id) -> ISMControlSpec: ...

@tool
def get_prior_cycle_summary(prior_run_id): ...

@tool
def get_rule_spec(rule_id) -> RuleSpec: ...
```

<div class="tree">
sfn.execution
└─ <span class="span-name">lambda.agent-narrator</span>
&nbsp;&nbsp;&nbsp;└─ <span class="span-name">strands.agent.loop</span>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ <span class="span-name">tool.get_finding</span> <span class="attr">[F-…0001]</span>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ <span class="span-name">tool.get_ism_control</span> <span class="attr">[ISM-1546]</span>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;├─ <span class="span-name">bedrock.invoke</span> <span class="attr">[in=4.2k out=1.1k tok]</span>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└─ <span class="span-name">tool.get_rule_spec</span> <span class="attr">[R3]</span>
</div>

</div>

⭐ **One env var unlocks all of this:** `STRANDS_TELEMETRY_ENABLED=true` → ADOT layer → X-Ray.

<!--
TIMING 10:30 → 12:00 (slide). Then live demo block.
Walk the tree LEFT-TO-RIGHT, top-to-bottom. Pause on bedrock.invoke — point at token counts.
Stage line: "Four tools. Read-only. The agent physically cannot disable an account, mutate state, or touch production. Adding a fifth tool is an architecture decision, not a commit."

⭐⭐⭐ DEMO BLOCK 1 (12:00 → 16:00) — see runbook § 3.1 (weekly run E2E).
⭐⭐⭐ DEMO BLOCK 2 (16:00 → 19:00) — see runbook § 3.2 (prompt injection → quarantine).
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Stage II challenge — five layers of hallucination defence

<div class="stack">
<div class="layer"><div class="n">L1</div><div class="name">Input constraint</div><div class="what">Raw rows never reach the model · temp=0 · structured output forced via tool-use</div></div>
<div class="layer"><div class="n">L2</div><div class="name">Runtime hard gates</div><div class="what">Schema · citation · reconciliation · entity-grounding · negation-consistency</div></div>
<div class="layer"><div class="n">L3</div><div class="name">Cross-model validation</div><div class="what">Haiku 4.5 judge · adversarial probe · self-consistency on CRITICAL findings</div></div>
<div class="layer"><div class="n">L4</div><div class="name">Offline evals (CI)</div><div class="what">Golden + adversarial + counterfactual + Hypothesis property tests block merge</div></div>
<div class="layer"><div class="n">L5</div><div class="name">Production drift</div><div class="what">Shadow evals · reviewer-disagreement loop · weekly KS test · circuit breaker</div></div>
</div>

> *"We can't make the agent never wrong. We can make it provably bounded."*

<!--
TIMING 19:00 → 21:00.
After demo 2 (prompt injection), this slide explains WHICH layer caught it: L2, citation gate.
Today's deployed surface: L1 + L2 + L3. Plan 2 ships L4. L5 is post-MVP.
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Prosecutor · Barrister · Judge

<div class="cols-3">
<div class="col-card">
<div class="num">Prosecutor</div>
<h3>Rules engine</h3>
<p>Brings the charges. Cites the law. <strong>No interpretation.</strong> Pure Python.</p>
</div>
<div class="col-card">
<div class="num">Barrister</div>
<h3>Strands agent</h3>
<p>Argues the case. Tells the story. <strong>Cannot invent evidence.</strong> Read-only tools, gated output.</p>
</div>
<div class="col-card">
<div class="num">Judge</div>
<h3>Reviewer (HITL)</h3>
<p>Decides: confirm risk · false positive · accepted exception. <strong>Always a human.</strong></p>
</div>
</div>

> *"Agent-with-guardrails is no longer a demo — it's a compliance posture."*

<!--
TIMING 21:00 → 22:30.
The closing intellectual hook. Slow down. This is the line audiences quote afterwards.
⭐ DEMO BLOCK 3 (22:30 → 23:30 if time) — monthly attestation + PDF + Object Lock — see runbook § 3.3.
-->

---

<!-- _class: bignum -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="label">The whole thing</div>

# $5

## per month. Six rules · five eval layers · seven-year trace retention.
*Cheaper than the coffee I had before walking on stage.*

<!--
TIMING 23:30 → 24:30.
Closing slide. Land the line. Then "Questions?"
Numbers are spec-derived. Don't volunteer the breakdown — only if asked.
-->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Thanks · Q&A

**Christina Chen** — Solution Architect, Banking & Finance, Mantel Group

`connie0972001@gmail.com` · LinkedIn `/in/christina-chen-au`

Source available on request · `github.com/cloudchristina/assessor-agent`

<div class="cols-3" style="margin-top:50px">
<div class="col-card"><h3>Ask me about</h3><p>Strands native OTel + X-Ray tool spans</p></div>
<div class="col-card"><h3>Ask me about</h3><p>The five gate Lambdas and the Haiku judge</p></div>
<div class="col-card"><h3>Ask me about</h3><p>The Plan 2 eval suite (50-case golden, in flight)</p></div>
</div>

<!--
Q&A slide stays up ~3-4 min during questions.
If asked anything you can't answer: "great question — I'll follow up by email." Hand out card. Never bluff in front of regulators-in-the-audience.
-->

---

<!-- _class: divider -->
<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

<div class="stagelabel">Backup</div>

# For Q&A only

<!-- The slides below are reference. Do NOT walk through unless asked. -->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Backup A — full architecture (Stage I + Stage II)

![full](./assets/diagrams/full-architecture.png)

<!-- Use only if asked "show me the whole pipeline". Walk top-to-bottom. -->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Backup B — the six rules in one frame

| # | Sev | Rule | ISM | Logic |
|---|---|---|---|---|
| **R1** | CRITICAL | SQL login with Admin access | 1546 | `login_type='SQL_LOGIN' AND access_level='Admin'` |
| **R2** | CRITICAL | Dormant privileged account | 1509/1555 | `Admin AND last_active > 90d` |
| **R3** | HIGH | SoD breach across DEV+PROD | 1175 | cross-DB aggregation by login |
| **R4** | HIGH | Orphaned login | 1555 | `mapped_user_name` empty everywhere |
| **R5** | HIGH | RBAC bypass | 0445 | explicit grant outside any role |
| **R6** | HIGH | Shared / generic account | 1545 | regex on `login_name` |

<!-- Use only if asked "what are the rules?". -->

---

<div class="mantel-mark"><img src="./assets/mantel/image1.png" alt=""><span>Mantel</span></div>

# Backup C — what's NOT in this demo

- Task-token attestation with reviewer ≠ attester quorum (SoD)
- SQL Server Audit → S3 for historical `last_active_date` (R2 correctness)
- Cognito group RBAC, exception register, SES + Slack notifications
- Plan 2 — full eval CI gate (in flight) · Plan 3 — frontend dashboard
- DDB Streams audit log · Macie · Security Hub · Grafana
- Shadow evals + drift KS tests (Layer 5)

**Demo scope ≠ design scope.** Spec Appendix B lists every cut.

<!-- Use only if asked "what would you add for production?". -->
