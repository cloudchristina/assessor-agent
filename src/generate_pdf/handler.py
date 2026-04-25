"""C13 — generate-attestation-pdf. Reads run + findings + narrative, writes PDF to S3."""
from __future__ import annotations
import json
from urllib.parse import urlparse
import boto3
from src.shared.logging import get_logger
from src.generate_pdf.templates import render_pdf

log = get_logger("generate-pdf")
s3 = boto3.client("s3")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def _report_key(run_id: str, started_at: str) -> str:
    # started_at is ISO8601 with Sydney offset in practice.
    yyyy_mm = started_at[:7] if started_at else "unknown"
    return f"reports/{yyyy_mm}/attestation_{run_id}.pdf"


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    run = {
        "run_id": event["run_id"],
        "cadence": event.get("cadence"),
        "started_at": event.get("started_at"),
        "trace_id": event.get("trace_id"),
        "manifest_sha256": event["manifest"]["row_ids_sha256"],
        "rows_scanned": event["manifest"]["row_count"],
        "findings_count": len(findings),
    }
    pdf_bytes = render_pdf(run, findings, narrative)
    key = _report_key(event["run_id"], event.get("started_at", ""))
    s3.put_object(
        Bucket=event["bucket"],
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ServerSideEncryption="aws:kms",
    )
    log.info("pdf.done", extra={"correlation_id": event["run_id"], "bytes": len(pdf_bytes)})
    return {
        "run_id": event["run_id"],
        "pdf_s3_uri": f"s3://{event['bucket']}/{key}",
        "bytes": len(pdf_bytes),
    }
