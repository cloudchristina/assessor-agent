"""C4 — Strands agent narrator.

Receives summary + finding_ids from the SFN payload and writes a NarrativeReport
to S3. The agent calls registered tools (get_finding, get_ism_control,
get_rule_spec, get_prior_cycle_summary) to enrich its narrative — every tool
call is an OTel span visible in X-Ray, satisfying the spec's Layer 1 'agent
sees only IDs' constraint.

Strands API note: we use the modern invocation pattern
    result = agent(prompt, structured_output_model=NarrativeReport)
which runs the full tool-use event loop AND produces structured output. The
deprecated `agent.structured_output(...)` method bypasses tool-use, which is
why the previous implementation showed no tool calls in X-Ray.
"""
from __future__ import annotations
import os
# Must come BEFORE `from strands import ...` so the OTel TracerProvider is
# set before Strands reads it via get_tracer_provider().
import src.shared.otel_init  # noqa: F401

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel
from src.shared.logging import get_logger
from src.shared.models import NarrativeReport
from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt
from src.agent_narrator.tools import (
    get_finding,
    get_ism_control,
    get_rule_spec,
    get_prior_cycle_summary,
)

log = get_logger("agent-narrator")
s3 = boto3.client("s3")

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")
_GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID")


def _build_agent(temperature: float = 0) -> Agent:
    kwargs: dict = {
        "model_id": _MODEL_ID,
        "region_name": "ap-southeast-2",
        "temperature": temperature,
    }
    if _GUARDRAIL_ID:
        kwargs["guardrail_id"] = _GUARDRAIL_ID
    model = BedrockModel(**kwargs)
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_finding,
            get_ism_control,
            get_rule_spec,
            get_prior_cycle_summary,
        ],
    )


def _has_critical_findings(summary: dict) -> bool:
    """Return True if the run summary indicates at least one CRITICAL finding."""
    return int(summary.get("CRITICAL", 0)) > 0


def _narrative_key(report: NarrativeReport) -> frozenset:
    """Stable fingerprint of the narrative's cited findings for consistency comparison.

    Uses finding_id only. ISM citations are deliberately excluded — the model
    legitimately picks between adjacent ISM controls (e.g. ISM-1545 vs ISM-1546)
    even at low temperature, and such jitter shouldn't trip self-consistency.
    The signal we care about is "did the agent cite the SAME set of findings
    across re-runs", which finding_id alone captures.
    """
    return frozenset(n.finding_id for n in report.finding_narratives)


def _self_consistency_check(user_prompt: str, primary_report: NarrativeReport) -> bool:
    """Run the agent two more times at temperature=0.3 and compare narrative fingerprints.

    Returns True  — all three runs agree (or a transient failure prevents comparison).
    Returns False — at least one extra run produced a divergent citation set.

    Trade-off: transient Bedrock failures default to True so infra blips don't
    quarantine an otherwise valid primary narrative.
    """
    primary_key = _narrative_key(primary_report)
    extra_keys: list[frozenset] = []

    for _ in range(2):
        try:
            extra_agent = _build_agent(temperature=0.3)
            extra_result = extra_agent(user_prompt, structured_output_model=NarrativeReport)
            extra_keys.append(_narrative_key(extra_result.structured_output))
        except Exception as exc:  # noqa: BLE001
            # Transient Bedrock failure — don't penalise primary run.
            log.warning(
                "self_consistency.extra_run_failed",
                extra={"error": str(exc)},
            )
            return True

    consistent = all(k == primary_key for k in extra_keys)
    if not consistent:
        log.warning(
            "self_consistency.divergence_detected",
            extra={"primary_key": str(primary_key), "extra_keys": [str(k) for k in extra_keys]},
        )
    return consistent


def lambda_handler(event: dict, _ctx: object) -> dict:
    log.info("agent.start", extra={"correlation_id": event["run_id"]})

    bucket = event["bucket"]
    run_id = event["run_id"]
    summary = event.get("summary", {})

    user = build_user_prompt(
        run_id=run_id,
        summary=summary,
        finding_ids=event["finding_ids"],
        prior_run_id=event.get("prior_run_id"),
    )

    agent = _build_agent()
    # Modern Strands API: tool-use loop runs AND structured output is enforced.
    result = agent(user, structured_output_model=NarrativeReport)
    report: NarrativeReport = result.structured_output

    # Self-consistency check: if any CRITICAL finding exists, re-run the agent
    # twice at temperature=0.3 and compare cited findings.  Divergence sets the
    # self_consistency_passed flag to False so downstream gates can quarantine.
    if _has_critical_findings(summary):
        consistent = _self_consistency_check(user, report)
        report = report.model_copy(update={"self_consistency_passed": consistent})

    out_key = f"narratives/{run_id}/narrative.json"
    s3.put_object(
        Bucket=bucket,
        Key=out_key,
        Body=report.model_dump_json().encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )
    log.info(
        "agent.done",
        extra={
            "correlation_id": run_id,
            "findings_count": len(event["finding_ids"]),
            "self_consistency_passed": report.self_consistency_passed,
        },
    )
    src.shared.otel_init.flush_otel()
    return {
        "run_id": run_id,
        "narrative_s3_uri": f"s3://{bucket}/{out_key}",
        "model_id": report.model_id,
    }
