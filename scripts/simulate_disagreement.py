"""CLI to update a finding's review/decision in DDB and trigger the reviewer-disagreement flow.

Usage:
    python -m scripts.simulate_disagreement \\
        --run-id=run_2026_04_25_abc \\
        --finding-id=finding_abc123 \\
        --decision=false_positive \\
        --reviewer-sub=test-reviewer \\
        --rationale="manual override for testing"
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import boto3


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Update a finding's review/decision in DDB to simulate reviewer disagreement."
        )
    )
    ap.add_argument("--run-id", required=True, help="Run ID (HASH key)")
    ap.add_argument("--finding-id", required=True, help="Finding ID (RANGE key)")
    ap.add_argument(
        "--decision",
        required=True,
        choices=["confirmed_risk", "false_positive", "accepted_exception", "escalated"],
        help="Reviewer decision",
    )
    ap.add_argument(
        "--reviewer-sub",
        default="cli-simulate",
        help="Reviewer subject (Cognito sub); defaults to 'cli-simulate'",
    )
    ap.add_argument(
        "--rationale",
        default="(simulated via scripts/simulate_disagreement.py)",
        help="Reviewer rationale",
    )
    ap.add_argument(
        "--findings-table",
        default=os.environ.get("FINDINGS_TABLE"),
        help="DDB table name; defaults to $FINDINGS_TABLE env var",
    )
    args = ap.parse_args()

    if not args.findings_table:
        print(
            "error: --findings-table is required (or set FINDINGS_TABLE env var)",
            file=sys.stderr,
        )
        return 2

    ddb = boto3.resource("dynamodb")
    table = ddb.Table(args.findings_table)

    decided_at = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    try:
        table.update_item(
            Key={"run_id": args.run_id, "finding_id": args.finding_id},
            UpdateExpression=(
                "SET decision = :d, reviewer_sub = :r, rationale = :rat, decided_at = :da"
            ),
            ExpressionAttributeValues={
                ":d": args.decision,
                ":r": args.reviewer_sub,
                ":rat": args.rationale,
                ":da": decided_at,
            },
            ReturnValues="ALL_NEW",
        )
        print(f"updated finding {args.finding_id} (run {args.run_id})")
        print(f"  decision: {args.decision}")
        print(f"  reviewer: {args.reviewer_sub}")
        print(f"  decided_at: {decided_at}")
        return 0
    except Exception as e:
        print(f"error updating finding: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
