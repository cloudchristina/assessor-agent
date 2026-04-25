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


def _build_agent() -> Agent:
    kwargs: dict = {
        "model_id": _MODEL_ID,
        "region_name": "ap-southeast-2",
        "temperature": 0,
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


def lambda_handler(event: dict, _ctx: object) -> dict:
    log.info("agent.start", extra={"correlation_id": event["run_id"]})

    bucket = event["bucket"]
    run_id = event["run_id"]

    user = build_user_prompt(
        run_id=run_id,
        summary=event["summary"],
        finding_ids=event["finding_ids"],
        prior_run_id=event.get("prior_run_id"),
    )

    agent = _build_agent()
    # Modern Strands API: tool-use loop runs AND structured output is enforced.
    result = agent(user, structured_output_model=NarrativeReport)
    report: NarrativeReport = result.structured_output

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
        },
    )
    return {
        "run_id": run_id,
        "narrative_s3_uri": f"s3://{bucket}/{out_key}",
        "model_id": report.model_id,
    }
