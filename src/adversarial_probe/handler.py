"""C8-probe — Adversarial probe Lambda.

Loads the narrative and findings from S3, then asks Bedrock Haiku to identify
the weakest / most suspect claim in the narrative.  Returns passed=True when
no claim's confidence exceeds the 0.7 threshold.
"""
from __future__ import annotations

import json
import os

# Must come BEFORE `from strands import ...` so the OTel TracerProvider is
# set before Strands reads it via get_tracer_provider().
import src.shared.otel_init  # noqa: F401

from urllib.parse import urlparse

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

from src.adversarial_probe.prompts import SYSTEM_PROMPT
from src.shared.logging import get_logger
from src.shared.models import WeakClaimsReport

log = get_logger("adversarial-probe")
s3 = boto3.client("s3")

_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "au.anthropic.claude-haiku-4-5-20251001-v1:0")
_CONFIDENCE_THRESHOLD = 0.7


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def _build_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=_MODEL_ID, region_name="ap-southeast-2", temperature=0),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
    )


def lambda_handler(event: dict, _ctx: object) -> dict:
    narrative_s3_uri = event["narrative_s3_uri"]
    findings_s3_uri = event["findings_s3_uri"]

    narrative = _read_json(narrative_s3_uri)
    findings = _read_json(findings_s3_uri).get("findings", [])

    user_prompt = json.dumps({"narrative": narrative, "findings": findings})

    agent = _build_agent()
    # Modern Strands API — emits OTel spans for the model call (the deprecated
    # structured_output() bypasses telemetry).
    result = agent(user_prompt, structured_output_model=WeakClaimsReport)
    report: WeakClaimsReport = result.structured_output

    max_confidence = max((c.confidence for c in report.weak_claims), default=0.0)
    passed = max_confidence <= _CONFIDENCE_THRESHOLD

    log.info(
        "adversarial_probe.done",
        extra={
            "passed": passed,
            "max_confidence": max_confidence,
            "weak_claims_count": len(report.weak_claims),
        },
    )
    src.shared.otel_init.flush_otel()

    return {
        "passed": passed,
        "passed_int": 1 if passed else 0,
        "weak_claims": [c.model_dump() for c in report.weak_claims],
    }
