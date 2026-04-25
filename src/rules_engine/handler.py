"""Lambda: read validated rows from S3, run all rules, write findings.json."""
from __future__ import annotations
import json
from urllib.parse import urlparse
import boto3
from src.shared.logging import get_logger
from src.shared.models import UARRow
from src.rules_engine.engine import run_rules
from src.rules_engine.rules import RULES

log = get_logger("rules-engine")
s3 = boto3.client("s3")


def lambda_handler(event: dict, _context: object) -> dict:
    log.info("rules.start", extra={"correlation_id": event["run_id"]})
    src = urlparse(event["rows_s3_uri"])
    obj = s3.get_object(Bucket=src.netloc, Key=src.path.lstrip("/"))
    payload = json.loads(obj["Body"].read())
    rows = [UARRow.model_validate(r) for r in payload.get("rows", [])]
    out = run_rules(rows=rows, run_id=event["run_id"], rules=RULES)
    out_key = f"rules/{event['run_id']}/findings.json"
    s3.put_object(
        Bucket=event["bucket"],
        Key=out_key,
        Body=out.model_dump_json().encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )
    log.info("rules.done", extra={"correlation_id": event["run_id"], "findings": len(out.findings)})
    return {
        "run_id": event["run_id"],
        "findings_s3_uri": f"s3://{event['bucket']}/{out_key}",
        "summary": out.summary,
        "findings_count": len(out.findings),
        "finding_ids": [f.finding_id for f in out.findings],  # consumed by agent-narrator state
    }
