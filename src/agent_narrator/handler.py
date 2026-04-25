"""C4 — Strands agent narrator. Receives summary+IDs, writes NarrativeReport to S3."""
from __future__ import annotations
import os
import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel
from src.shared.logging import get_logger
from src.shared.models import NarrativeReport
from src.agent_narrator.tools import (
    get_finding,
    get_ism_control,
    get_rule_spec,
    get_prior_cycle_summary,
)
from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt

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
        tools=[get_finding, get_ism_control, get_rule_spec, get_prior_cycle_summary],
    )


def lambda_handler(event: dict, _ctx: object) -> dict:
    log.info("agent.start", extra={"correlation_id": event["run_id"]})
    agent = _build_agent()
    user = build_user_prompt(
        run_id=event["run_id"],
        summary=event["summary"],
        finding_ids=event["finding_ids"],
        prior_run_id=event.get("prior_run_id"),
    )
    report: NarrativeReport = agent.structured_output(NarrativeReport, user)
    out_key = f"narratives/{event['run_id']}/narrative.json"
    s3.put_object(
        Bucket=event["bucket"],
        Key=out_key,
        Body=report.model_dump_json().encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )
    log.info(
        "agent.done",
        extra={
            "correlation_id": event["run_id"],
            "tokens_in": getattr(agent, "input_tokens", None),
            "tokens_out": getattr(agent, "output_tokens", None),
        },
    )
    return {
        "run_id": event["run_id"],
        "narrative_s3_uri": f"s3://{event['bucket']}/{out_key}",
        "model_id": report.model_id,
    }
