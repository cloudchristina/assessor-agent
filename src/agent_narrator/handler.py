"""C4 — Strands agent narrator. Receives summary+IDs, writes NarrativeReport to S3.

Implementation note: Strands' structured_output is most reliable as a
single-turn call, so the handler pre-fetches the findings + ISM control
catalogue entries from S3 and the local catalogue, then passes them
inline. This trades the spec's "tool-only access" purity for reliability
— Sonnet 4.6 with multi-turn tool use kept responding in plain text and
never invoked the schema tool, breaking structured_output.
"""
from __future__ import annotations
import json
import os
from urllib.parse import urlparse
import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel
from src.shared.logging import get_logger
from src.shared.ism_controls import get_ism_control as _get_ism
from src.shared.models import NarrativeReport
from src.rules_engine.rules import RULES
from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt

log = get_logger("agent-narrator")
s3 = boto3.client("s3")

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-6")
_GUARDRAIL_ID = os.environ.get("BEDROCK_GUARDRAIL_ID")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def _build_agent() -> Agent:
    kwargs: dict = {
        "model_id": _MODEL_ID,
        "region_name": "ap-southeast-2",
        "temperature": 0,
    }
    if _GUARDRAIL_ID:
        kwargs["guardrail_id"] = _GUARDRAIL_ID
    model = BedrockModel(**kwargs)
    # No runtime tools — everything is bundled into the user prompt so
    # structured_output is one-shot.
    return Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=[])


def _gather_context(findings: list[dict]) -> dict:
    control_ids = sorted({c for f in findings for c in f.get("ism_controls", [])})
    controls = []
    for cid in control_ids:
        try:
            spec = _get_ism(cid)
            controls.append({"control_id": spec.control_id, "title": spec.title, "intent": spec.intent})
        except KeyError:
            controls.append({"control_id": cid, "title": "(unknown)", "intent": "(unknown)"})

    rule_ids = sorted({f["rule_id"] for f in findings})
    rules = []
    for rid in rule_ids:
        for r in RULES:
            if r.rule_id == rid:
                rules.append({
                    "rule_id": r.rule_id,
                    "severity": r.severity,
                    "ism_controls": list(r.ism_controls),
                    "description": r.description,
                })
                break
    return {"controls": controls, "rules": rules}


def lambda_handler(event: dict, _ctx: object) -> dict:
    log.info("agent.start", extra={"correlation_id": event["run_id"]})

    bucket = event["bucket"]
    run_id = event["run_id"]
    findings_s3_uri = event.get("findings_s3_uri") or f"s3://{bucket}/rules/{run_id}/findings.json"
    findings = _read_json(findings_s3_uri).get("findings", [])
    context = _gather_context(findings)

    agent = _build_agent()
    user = build_user_prompt(
        run_id=run_id,
        summary=event["summary"],
        finding_ids=event["finding_ids"],
        prior_run_id=event.get("prior_run_id"),
        findings=findings,
        ism_controls=context["controls"],
        rules=context["rules"],
    )
    report: NarrativeReport = agent.structured_output(NarrativeReport, user)
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
            "findings_count": len(findings),
        },
    )
    return {
        "run_id": run_id,
        "narrative_s3_uri": f"s3://{bucket}/{out_key}",
        "model_id": report.model_id,
    }
