"""C7 — Judge Lambda. Bedrock Haiku 4.5 evaluates narrative vs findings."""
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
from src.shared.logging import get_logger
from src.shared.models import JudgeScore
from src.judge.prompts import SYSTEM_PROMPT

log = get_logger("judge")
s3 = boto3.client("s3")
_MODEL_ID = os.environ.get("JUDGE_MODEL_ID", "anthropic.claude-haiku-4-5")
_THRESHOLDS = {"faithfulness": 0.9, "completeness": 0.95, "fabrication": 0.05}


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def _passed(score: JudgeScore) -> bool:
    return (
        score.faithfulness >= _THRESHOLDS["faithfulness"]
        and score.completeness >= _THRESHOLDS["completeness"]
        and score.fabrication <= _THRESHOLDS["fabrication"]
    )


def _build_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=_MODEL_ID, region_name="ap-southeast-2", temperature=0),
        system_prompt=SYSTEM_PROMPT,
        tools=[],
    )


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    user = json.dumps({"findings": findings, "narrative": narrative})
    agent = _build_agent()
    # Modern Strands API — emits OTel spans for the model call (the deprecated
    # structured_output() bypasses telemetry).
    result = agent(user, structured_output_model=JudgeScore)
    score: JudgeScore = result.structured_output
    passed = _passed(score)
    log.info("judge.done", extra={"passed": passed, **score.model_dump(exclude={"reasoning"})})
    return {
        "gate": "judge",
        "passed": passed,
        "passed_int": 1 if passed else 0,
        **score.model_dump(),
    }
