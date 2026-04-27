"""Shadow-eval Lambda: re-judges new runs with latest model and writes drift signals."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3

from src.shared.logging import get_logger

log = get_logger("shadow-eval")
_lambda = boto3.client("lambda")
_ddb = boto3.resource("dynamodb")


def lambda_handler(event: dict, _ctx: object) -> dict:
    """Process DDB stream events for the `runs` table.

    For each INSERT record:
      1. Extract the run document from the NewImage wire format.
      2. Re-invoke the judge Lambda with the same S3 URIs.
      3. If |new_faithfulness - old_faithfulness| > threshold, write a drift
         signal row to the drift_signals DDB table.
    """
    drift_table = _ddb.Table(os.environ["DRIFT_SIGNALS_TABLE"])
    threshold = float(os.environ.get("SHADOW_DRIFT_THRESHOLD", "0.10"))
    judge_fn = os.environ["JUDGE_FUNCTION_NAME"]
    signals_written = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue

        new_image = record.get("dynamodb", {}).get("NewImage", {})
        run = _deserialize_image(new_image)

        if not run.get("narrative_s3_uri") or not run.get("findings_s3_uri"):
            log.info("shadow_eval.skip_missing_uris", extra={"run_id": run.get("run_id")})
            continue

        old_faith = float(
            run.get("judge_score", {}).get("faithfulness", 0.0)
        )
        new_faith = _reinvoke_judge(judge_fn, run["narrative_s3_uri"], run["findings_s3_uri"])

        if new_faith is None:
            continue  # transient invocation failure — skip silently

        delta = new_faith - old_faith
        if abs(delta) > threshold:
            _write_drift_signal(drift_table, run["run_id"], old_faith, new_faith, delta)
            signals_written += 1

    return {
        "records_processed": len(event.get("Records", [])),
        "signals_written": signals_written,
    }


def _deserialize_image(image: dict) -> dict:
    """Convert a DDB Streams NewImage wire format to a plain Python dict.

    Wire format: ``{"key": {"S": "value"}, "num": {"N": "1.23"}, ...}``
    """
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


def _reinvoke_judge(judge_fn: str, narrative_uri: str, findings_uri: str) -> float | None:
    """Invoke the judge Lambda and return the faithfulness score, or None on failure."""
    try:
        resp = _lambda.invoke(
            FunctionName=judge_fn,
            Payload=json.dumps(
                {
                    "narrative_s3_uri": narrative_uri,
                    "findings_s3_uri": findings_uri,
                }
            ),
        )
        payload = json.loads(resp["Payload"].read())
        return float(payload.get("faithfulness", 0.0))
    except Exception as exc:
        log.warning("shadow_eval.judge_invoke_failed", extra={"error": str(exc)})
        return None


def _write_drift_signal(
    table: Any,
    run_id: str,
    old: float,
    new: float,
    delta: float,
) -> None:
    """Persist a drift signal row to the drift_signals DDB table."""
    item = {
        "signal_id": f"shadow_{run_id}_{uuid.uuid4().hex[:6]}",
        "detected_at": datetime.now(UTC).isoformat(),
        "signal_type": "shadow_drift",
        "metric_name": "faithfulness",
        "delta": delta,
        "details": {
            "run_id": run_id,
            "old_faithfulness": old,
            "new_faithfulness": new,
        },
        "ttl": int(time.time()) + (90 * 24 * 3600),  # 90-day TTL
    }
    # DynamoDB rejects raw Python floats — convert via JSON round-trip.
    safe = json.loads(json.dumps(item, default=str), parse_float=Decimal)
    table.put_item(Item=safe)
    log.info(
        "shadow_eval.drift_signal_written",
        extra={"signal_id": item["signal_id"], "delta": delta},
    )
