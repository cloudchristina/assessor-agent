"""Reviewer-disagreement Lambda: appends golden-set candidates when triage diverges from severity."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from src.shared.logging import get_logger

log = get_logger("reviewer-disagreement")
_ddb = boto3.resource("dynamodb")


def lambda_handler(event: dict, _ctx: object) -> dict:
    table = _ddb.Table(os.environ["GOLDEN_SET_CANDIDATES_TABLE"])
    written = 0
    for record in event.get("Records", []):
        if record.get("eventName") != "MODIFY":
            continue
        new = _deserialize_image(record.get("dynamodb", {}).get("NewImage", {}))
        old = _deserialize_image(record.get("dynamodb", {}).get("OldImage", {}))
        if not _has_review_change(new, old):
            continue
        if not _is_disagreement(new):
            continue
        _write_candidate(table, new)
        written += 1
    return {"records_processed": len(event.get("Records", [])), "candidates_written": written}


def _has_review_change(new: dict, old: dict) -> bool:
    """True if review/decision changed in this MODIFY."""
    return new.get("decision") != old.get("decision") and new.get("decision") is not None


def _is_disagreement(finding: dict) -> bool:
    sev = finding.get("severity")
    decision = finding.get("decision")
    if sev == "CRITICAL" and decision == "false_positive":
        return True
    if sev == "LOW" and decision == "confirmed_risk":
        return True
    return False


def _write_candidate(table: Any, finding: dict) -> None:
    item = {
        "candidate_id": (
            f"cand_{finding.get('run_id', '?')}_{finding.get('finding_id', '?')}"
            f"_{uuid.uuid4().hex[:6]}"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "run_id": finding.get("run_id"),
        "finding_id": finding.get("finding_id"),
        "rule_id": finding.get("rule_id"),
        "expected_severity": finding.get("severity"),
        "decision": finding.get("decision"),
        "reviewer_sub": finding.get("reviewer_sub"),
        "rationale": finding.get("rationale"),
    }
    safe = json.loads(json.dumps(item, default=str), parse_float=Decimal)
    table.put_item(Item=safe)
    log.info(
        "reviewer_disagreement.candidate_written",
        extra={"candidate_id": item["candidate_id"]},
    )


def _deserialize_image(image: dict) -> dict:
    """DDB Stream NewImage/OldImage wire format -> plain Python dict."""
    out: dict[str, Any] = {}
    for k, v in image.items():
        if "S" in v:
            out[k] = v["S"]
        elif "N" in v:
            out[k] = float(v["N"])
        elif "M" in v:
            out[k] = _deserialize_image(v["M"])
        elif "L" in v:
            out[k] = [_deserialize_image({"_": item})["_"] for item in v["L"]]
        elif "BOOL" in v:
            out[k] = v["BOOL"]
        elif "NULL" in v:
            out[k] = None
    return out
