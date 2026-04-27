"""Weekly drift detector: KS test on judge faithfulness over last 7 vs prior 30 days."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

from src.drift_detector.ks_test import ks_drift
from src.shared.logging import get_logger

log = get_logger("drift-detector")
_ddb = boto3.resource("dynamodb")


def lambda_handler(event: dict, _ctx: object) -> dict:
    runs_table = _ddb.Table(os.environ["RUNS_TABLE"])
    drift_table = _ddb.Table(os.environ["DRIFT_SIGNALS_TABLE"])
    alpha = float(os.environ.get("DRIFT_ALPHA", "0.05"))

    now = datetime.now(timezone.utc)
    recent_cutoff = (now - timedelta(days=7)).isoformat()
    baseline_start = (now - timedelta(days=37)).isoformat()
    baseline_end = recent_cutoff  # baseline is days 7..37

    recent = _query_faithfulness(runs_table, recent_cutoff, now.isoformat())
    baseline = _query_faithfulness(runs_table, baseline_start, baseline_end)

    ks = ks_drift(recent, baseline, alpha=alpha)
    log.info(
        "drift_detector.ks_result",
        extra={
            "statistic": ks.statistic,
            "pvalue": ks.pvalue,
            "drift_detected": ks.drift_detected,
            "n_recent": ks.n_recent,
            "n_baseline": ks.n_baseline,
        },
    )
    if ks.drift_detected:
        _write_drift_signal(drift_table, ks)
        return {
            "drift_detected": True,
            "statistic": ks.statistic,
            "pvalue": ks.pvalue,
        }
    return {
        "drift_detected": False,
        "statistic": ks.statistic,
        "pvalue": ks.pvalue,
    }


def _query_faithfulness(table, start_iso: str, end_iso: str) -> list[float]:
    """Scan runs table for runs in [start, end] and extract judge_score.faithfulness.

    NOTE: Scan with FilterExpression — for a real production deployment, use a GSI on
    started_at. For this demo + the volume we expect, scan is acceptable.
    """
    resp = table.scan(
        FilterExpression="started_at BETWEEN :s AND :e",
        ExpressionAttributeValues={":s": start_iso, ":e": end_iso},
    )
    out: list[float] = []
    for item in resp.get("Items", []):
        score = item.get("judge_score", {})
        if isinstance(score, dict) and "faithfulness" in score:
            try:
                out.append(float(score["faithfulness"]))
            except (TypeError, ValueError):
                continue
    return out


def _write_drift_signal(table, ks) -> None:
    item = {
        "signal_id": f"ks_{uuid.uuid4().hex[:10]}",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "signal_type": "ks_drift",
        "metric_name": "faithfulness",
        "delta": ks.statistic,
        "details": {
            "statistic": ks.statistic,
            "pvalue": ks.pvalue,
            "n_recent": ks.n_recent,
            "n_baseline": ks.n_baseline,
        },
        "ttl": int(time.time()) + (90 * 24 * 3600),
    }
    safe = json.loads(json.dumps(item, default=str), parse_float=Decimal)
    table.put_item(Item=safe)
    log.info("drift_detector.signal_written", extra={"signal_id": item["signal_id"]})
