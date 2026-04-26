"""Weekly digest of pending reviewer-disagreement candidates."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import boto3

from src.shared.logging import get_logger

log = get_logger("reviewer-disagreement-digest")
ddb = boto3.resource("dynamodb")
ses = boto3.client("ses")


def lambda_handler(event: dict, _ctx: object) -> dict:
    table = ddb.Table(os.environ["GOLDEN_SET_CANDIDATES_TABLE"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    items = table.scan(
        FilterExpression="#s = :p AND created_at >= :c",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":p": "pending", ":c": cutoff},
    ).get("Items", [])
    body = _format(items)
    ses.send_email(
        Source=os.environ["DIGEST_FROM"],
        Destination={"ToAddresses": [os.environ["COMPLIANCE_EMAIL"]]},
        Message={
            "Subject": {"Data": f"Reviewer-disagreement digest ({len(items)} pending)"},
            "Body": {"Text": {"Data": body}},
        },
    )
    log.info("digest.sent", extra={"count": len(items)})
    return {"sent": True, "count": len(items)}


def _format(items: list[dict]) -> str:
    if not items:
        return "No pending reviewer-disagreement candidates this week."
    lines = [f"{len(items)} pending candidates:\n"]
    for it in items:
        lines.append(
            f"- {it.get('candidate_id')} [{it.get('expected_severity')}] "
            f"{it.get('finding_id')} — decision={it.get('decision')} "
            f"rationale={it.get('rationale')!r}"
        )
    return "\n".join(lines)
