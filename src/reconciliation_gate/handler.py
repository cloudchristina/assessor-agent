"""C6 — reconciliation gate.

Asserts narrative.total_findings == len(findings) AND set equality between
cited_ids and findings_ids. Reasons returned: `count_mismatch`, `set_mismatch`.
"""
from __future__ import annotations
import json
from urllib.parse import urlparse
import boto3
from src.shared.logging import get_logger

log = get_logger("reconciliation-gate")
s3 = boto3.client("s3")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    findings_ids = {f["finding_id"] for f in findings}
    cited_ids = {n["finding_id"] for n in narrative.get("finding_narratives", [])}
    total_findings = narrative.get("total_findings", -1)
    reasons: list[str] = []
    if total_findings != len(findings):
        reasons.append("count_mismatch")
    if findings_ids != cited_ids:
        reasons.append("set_mismatch")
    passed = not reasons
    log.info("reconciliation.gate", extra={"passed": passed, "reasons": reasons})
    return {
        "gate": "reconciliation",
        "passed": passed,
        "passed_int": 1 if passed else 0,
        "reasons": reasons,
        "narrative_total": total_findings,
        "findings_count": len(findings),
    }
