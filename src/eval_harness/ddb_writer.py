"""Persist eval results + load baselines from the eval_results DDB table."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3


def _table():
    return boto3.resource("dynamodb").Table(os.environ["EVAL_RESULTS_TABLE"])


def write_eval_result(
    eval_run_id: str,
    case_id: str,
    metrics: dict[str, Any],
    *,
    branch: str,
    commit_sha: str,
    case_type: str = "golden",
) -> None:
    """Persist one eval-result row. Floats wrapped via Decimal per DDB constraints."""
    item = {
        "eval_run_id": eval_run_id,
        "case_id": case_id,
        "branch": branch,
        "commit_sha": commit_sha,
        "case_type": case_type,
        "metrics": metrics,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    safe = json.loads(json.dumps(item, default=str), parse_float=Decimal)
    _table().put_item(Item=safe)


def load_baseline_for_branch(branch: str) -> dict | None:
    """Return the most-recent aggregated eval result for `branch`, or None."""
    try:
        resp = _table().query(
            IndexName="branch_index",
            KeyConditionExpression="#b = :b",
            ExpressionAttributeNames={"#b": "branch"},
            ExpressionAttributeValues={":b": branch},
            ScanIndexForward=False,  # newest first
            Limit=1,
        )
    except Exception:
        return None
    items = resp.get("Items", [])
    if not items:
        return None
    item = items[0]
    # Convert Decimal back to float for downstream JSON serialisation
    return json.loads(json.dumps(item, default=_decimal_default))


def _decimal_default(o: object) -> float:
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(repr(o))
