"""C9 — publish-triage. Writes runs + findings to DDB."""
from __future__ import annotations
import json
import os
from decimal import Decimal
from urllib.parse import urlparse
from datetime import datetime, timezone
import boto3
from src.shared.logging import get_logger

log = get_logger("publish-triage")
ddb = boto3.resource("dynamodb")
s3 = boto3.client("s3")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def _ddb_ready(value):
    """Round-trip through JSON so floats become Decimal, which DDB requires."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    runs = ddb.Table(os.environ["RUNS_TABLE"])
    finds = ddb.Table(os.environ["FINDINGS_TABLE"])
    nid = {n["finding_id"]: n for n in narrative.get("finding_narratives", [])}
    runs.put_item(Item=_ddb_ready({
        "run_id": event["run_id"],
        "cadence": event["cadence"],
        "started_at": event["started_at"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "succeeded" if event["all_gates_passed"] else "quarantined",
        "manifest_sha256": event["manifest"]["row_ids_sha256"],
        "rows_scanned": event["manifest"]["row_count"],
        "findings_count": len(findings),
        "judge_score": event["judge_score"],
        "gates": event["gates"],
        "narrative_s3_uri": event["narrative_s3_uri"],
        "trace_id": event.get("trace_id"),
    }))
    with finds.batch_writer() as bw:
        for f in findings:
            n = nid.get(f["finding_id"], {})
            bw.put_item(Item=_ddb_ready({
                **f,
                "narrative": n.get("group_theme") or "",
                "remediation": n.get("remediation") or "",
                "review": {"status": "pending"},
            }))
    log.info("publish.done", extra={"correlation_id": event["run_id"], "findings": len(findings)})
    return {"run_id": event["run_id"], "findings_count": len(findings)}
