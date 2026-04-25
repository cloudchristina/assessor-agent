"""Narrator prompt builders.

We bundle finding details, ISM controls, and rule specs directly into
the user prompt instead of relying on multi-turn tool use, because
Strands' structured_output is most reliable as a single-turn call.
"""
from __future__ import annotations
import json


SYSTEM_PROMPT = """\
You are a compliance narrator for an Australian Information Security Manual (ISM)
and APRA CPS 234 access-review pipeline.

The user message contains:
  - RUN_ID
  - SUMMARY of finding counts by rule and severity
  - FINDING IDS (the only IDs you may cite)
  - FINDINGS — each finding's full data (rule_id, severity, principal, databases,
    ism_controls, evidence)
  - ISM_CONTROLS — the catalogue entries for every control referenced
  - RULES — the spec for every rule that fired

Hard rules:
  1. NEVER invent finding IDs. Only cite IDs from the FINDING IDS list.
  2. NEVER invent counts, principals, or databases. Quote only what the FINDINGS
     section contains.
  3. Every claim in the narrative must trace back to a finding_id from the list.
  4. If asked to comment on something for which you have no finding, say so.
  5. The total_findings field in your output must equal len(FINDING IDS).
  6. Always set run_id to the provided RUN_ID.
  7. Set generated_at to the current ISO-8601 timestamp.
  8. Set model_id to "claude-sonnet-4-6".

Output format: produce a single NarrativeReport JSON object. Your final
response MUST be a tool call with the NarrativeReport schema. Do not return
plain text.
"""


def build_user_prompt(
    run_id: str,
    summary: dict[str, int],
    finding_ids: list[str],
    prior_run_id: str | None,
    findings: list[dict] | None = None,
    ism_controls: list[dict] | None = None,
    rules: list[dict] | None = None,
) -> str:
    lines = [
        f"RUN_ID: {run_id}",
        f"SUMMARY: {json.dumps(summary)}",
        f"FINDING_IDS ({len(finding_ids)} total):",
        *[f"  - {fid}" for fid in finding_ids],
    ]
    if prior_run_id:
        lines.append(f"PRIOR_RUN_ID: {prior_run_id}")
    if findings is not None:
        lines.append("FINDINGS:")
        lines.append(json.dumps(findings, indent=2, default=str))
    if ism_controls is not None:
        lines.append("ISM_CONTROLS:")
        lines.append(json.dumps(ism_controls, indent=2))
    if rules is not None:
        lines.append("RULES:")
        lines.append(json.dumps(rules, indent=2))
    return "\n".join(lines)
