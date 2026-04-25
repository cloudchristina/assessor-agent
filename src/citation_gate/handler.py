"""C5 — citation gate. Every cited finding_id must exist in findings set."""
from __future__ import annotations
import json
from urllib.parse import urlparse
import boto3
from src.shared.logging import get_logger

log = get_logger("citation-gate")
s3 = boto3.client("s3")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    findings_ids = {f["finding_id"] for f in findings}
    cited = {n["finding_id"] for n in narrative.get("finding_narratives", [])}
    missing = sorted(cited - findings_ids)
    extra = sorted(findings_ids - cited)
    passed = not missing
    log.info("citation.gate", extra={"passed": passed, "missing": len(missing)})
    return {
        "gate": "citation",
        "passed": passed,
        "passed_int": 1 if passed else 0,
        "missing_ids": missing,
        "extra_ids": extra,
    }
