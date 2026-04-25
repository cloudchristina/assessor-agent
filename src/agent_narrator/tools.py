"""Strands tools — read-only. Adding a tool here is an architecture decision."""
from __future__ import annotations
import json
import os
from typing import Any
import boto3
from strands import tool
from src.shared.ism_controls import get_ism_control as _get_ism
from src.rules_engine.rules import RULES


def _ddb_table() -> Any:
    return boto3.resource("dynamodb").Table(os.environ["FINDINGS_TABLE"])


def _s3_client() -> Any:
    return boto3.client("s3")


@tool
def get_finding(run_id: str, finding_id: str) -> dict:
    """Return the full finding for (run_id, finding_id). Both must come from the
    Finding IDs list passed in the user prompt — do not invent IDs."""
    resp = _ddb_table().get_item(Key={"run_id": run_id, "finding_id": finding_id})
    return resp.get("Item", {})


@tool
def get_ism_control(control_id: str) -> dict:
    """Return ISM control catalogue entry."""
    spec = _get_ism(control_id)
    return {"control_id": spec.control_id, "title": spec.title, "intent": spec.intent}


@tool
def get_rule_spec(rule_id: str) -> dict:
    """Return rule metadata (severity, ISM controls, description)."""
    for r in RULES:
        if r.rule_id == rule_id:
            return {
                "rule_id": r.rule_id,
                "severity": r.severity,
                "ism_controls": list(r.ism_controls),
                "description": r.description,
            }
    raise KeyError(rule_id)


@tool
def get_prior_cycle_summary(prior_run_id: str) -> dict:
    """Return previous cycle's RulesEngineOutput summary."""
    bucket = os.environ["RUNS_BUCKET"]
    obj = _s3_client().get_object(Bucket=bucket, Key=f"rules/{prior_run_id}/findings.json")
    return json.loads(obj["Body"].read())
