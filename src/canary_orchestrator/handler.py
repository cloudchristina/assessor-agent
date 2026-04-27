"""Canary orchestrator Lambda — Layer 5 production drift detection.

Triggered weekly by EventBridge Scheduler (configured in Task 7.7).

For each canary baseline:
  1. Uploads the fixture CSV to the synthetic-input S3 bucket.
  2. Starts a Step Functions execution with the fixture as the synthetic input.
  3. Polls until the execution completes (SUCCEEDED / FAILED).
  4. Reads the resulting run record from DDB.
  5. Compares actual metrics to the baseline JSON tolerances.
  6. Writes a canary_results row; drift_detected=True if any metric breaches tolerance.

Env vars (all required unless defaulted):
  STATE_MACHINE_ARN      — SFN to invoke
  CANARY_RESULTS_TABLE   — DDB table to write canary results to
  RUNS_TABLE             — DDB table to read run records from
  SYNTHETIC_INPUT_BUCKET — S3 bucket for fixture uploads
  CANARY_BASELINES_DIR   — local path to baseline JSONs (default: evals/canary/baselines)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import boto3

from src.shared.logging import get_logger

log = get_logger("canary-orchestrator")

# Module-level AWS clients (mocked in tests via patch).
sfn = boto3.client("stepfunctions")
s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASELINES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "evals/canary/baselines"
)
_POLL_INTERVAL_SEC = 5
_MAX_POLL_ATTEMPTS = 120  # 10 minutes max per fixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ddb_ready(value: object) -> object:
    """Round-trip through JSON to convert floats → Decimal for DDB."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _load_baselines(baselines_dir: Path) -> list[dict]:
    """Load all *.json baseline files from the baselines directory."""
    files = sorted(baselines_dir.glob("*.json"))
    baselines = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            baselines.append(data)
        except Exception as exc:
            log.warning("canary.baseline.load_error", extra={"file": str(f), "error": str(exc)})
    return baselines


def _upload_fixture(bucket: str, month: str, fixture_path: str) -> str:
    """Upload the fixture CSV to S3 and return the s3:// URI."""
    key = f"canary/fixtures/{month}.csv"
    s3.upload_file(fixture_path, bucket, key)
    return f"s3://{bucket}/{key}"


def _start_execution(state_machine_arn: str, run_id: str, s3_uri: str) -> str:
    """Start an SFN execution and return the execution ARN."""
    resp = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=run_id,
        input=json.dumps({
            "cadence": "weekly",
            "started_at": datetime.now(UTC).isoformat(),
            "synthetic_input_s3_uri": s3_uri,
            "run_id": run_id,
        }),
    )
    return resp["executionArn"]


def _wait_for_completion(execution_arn: str) -> dict:
    """Poll SFN until execution SUCCEEDED/FAILED. Returns describe_execution response."""
    for _attempt in range(_MAX_POLL_ATTEMPTS):
        resp = sfn.describe_execution(executionArn=execution_arn)
        status = resp["status"]
        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return resp
        time.sleep(_POLL_INTERVAL_SEC)
    # If we exit the loop without a terminal state, return the last response.
    return sfn.describe_execution(executionArn=execution_arn)


def _fetch_run_record(runs_table_name: str, run_id: str) -> dict | None:
    """Fetch the run record from DDB by run_id. Returns None if not found."""
    table = ddb.Table(runs_table_name)
    resp = table.get_item(Key={"run_id": run_id})
    return resp.get("Item")


def _check_drift(actual_metrics: dict, baseline: dict) -> tuple[bool, dict]:
    """Compare actual metrics to baseline + tolerances.

    Returns (drift_detected, drift_details).
    drift_details maps metric_name → {actual, baseline_value, threshold, breached}.
    """
    expected = baseline.get("expected_metrics", {})
    tolerance = baseline.get("tolerance", {})
    drift_details: dict[str, dict] = {}
    drift_detected = False

    for metric_name, tol in tolerance.items():
        baseline_value = expected.get(metric_name)
        actual_value = actual_metrics.get(metric_name)
        if baseline_value is None or actual_value is None:
            continue
        # Convert Decimal to float for comparison
        bv = float(baseline_value)
        av = float(actual_value)
        threshold = bv - float(tol)
        breached = av < threshold
        if breached:
            drift_detected = True
        drift_details[metric_name] = {
            "actual": av,
            "baseline_value": bv,
            "threshold": threshold,
            "breached": breached,
        }

    return drift_detected, drift_details


def _actual_metrics_from_run(run_record: dict) -> dict:
    """Extract comparable metrics from a DDB run record."""
    judge_score = run_record.get("judge_score") or {}
    return {
        "judge_faithfulness": float(judge_score.get("faithfulness", 0.0)),
        "judge_completeness": float(judge_score.get("completeness", 0.0)),
        "total_findings": int(run_record.get("findings_count", 0)),
    }


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, _ctx: object) -> dict:
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    canary_results_table = os.environ["CANARY_RESULTS_TABLE"]
    runs_table = os.environ["RUNS_TABLE"]
    bucket = os.environ["SYNTHETIC_INPUT_BUCKET"]
    baselines_dir = Path(os.environ.get("CANARY_BASELINES_DIR", str(_DEFAULT_BASELINES_DIR)))

    canary_run_id = f"canary-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(UTC).isoformat()

    log.info(
        "canary.start",
        extra={"canary_run_id": canary_run_id, "baselines_dir": str(baselines_dir)},
    )

    baselines = _load_baselines(baselines_dir)
    results_table = ddb.Table(canary_results_table)

    fixtures_processed = 0
    drift_detected_count = 0
    summary: list[dict] = []

    for baseline in baselines:
        month = baseline["month"]
        fixture_rel = baseline["fixture"]

        # Resolve fixture path.
        # Stored paths are relative to the repo root (e.g. "evals/canary/fixtures/...").
        # baselines_dir structure: <repo_root>/evals/canary/baselines
        #   parent x1 = evals/canary
        #   parent x2 = evals
        #   parent x3 = <repo_root>
        fixture_path = Path(fixture_rel)
        if not fixture_path.is_absolute():
            repo_root = baselines_dir.parent.parent.parent
            fixture_path = repo_root / fixture_rel

        if not fixture_path.exists():
            log.warning("canary.fixture.missing", extra={"month": month, "path": str(fixture_path)})
            continue

        # 1. Upload fixture to S3
        s3_uri = _upload_fixture(bucket, month, str(fixture_path))

        # 2. Start SFN execution
        run_id = f"canary-{month}-{uuid.uuid4().hex[:8]}"
        try:
            execution_arn = _start_execution(state_machine_arn, run_id, s3_uri)
        except Exception as exc:
            log.error("canary.sfn.start_failed", extra={"month": month, "error": str(exc)})
            continue

        # 3. Wait for completion
        exec_resp = _wait_for_completion(execution_arn)
        exec_status = exec_resp["status"]

        # Extract run_id from SFN output if available
        if exec_status == "SUCCEEDED" and "output" in exec_resp:
            try:
                sfn_output = json.loads(exec_resp["output"])
                run_id = sfn_output.get("run_id", run_id)
            except (json.JSONDecodeError, KeyError):
                pass

        # 4. Fetch run record from DDB
        run_record = _fetch_run_record(runs_table, run_id) or {}

        # 5. Compute actual metrics + drift
        actual_metrics = _actual_metrics_from_run(run_record)
        drift_detected, drift_details = _check_drift(actual_metrics, baseline)

        if drift_detected:
            drift_detected_count += 1
            log.warning(
                "canary.drift_detected",
                extra={
                    "canary_run_id": canary_run_id,
                    "month": month,
                    "drift_details": drift_details,
                },
            )

        # 6. Write canary_results row
        row = _ddb_ready({
            "canary_run_id": canary_run_id,
            "month": month,
            "started_at": started_at,
            "sfn_status": exec_status,
            "actual_metrics": actual_metrics,
            "baseline_metrics": baseline.get("expected_metrics", {}),
            "drift_detected": drift_detected,
            "drift_details": drift_details,
        })
        results_table.put_item(Item=row)  # type: ignore[arg-type]

        fixtures_processed += 1
        summary.append({
            "month": month,
            "drift_detected": drift_detected,
            "sfn_status": exec_status,
        })

        log.info(
            "canary.fixture.done",
            extra={
                "canary_run_id": canary_run_id,
                "month": month,
                "drift_detected": drift_detected,
                "actual_metrics": actual_metrics,
            },
        )

    result = {
        "canary_run_id": canary_run_id,
        "fixtures_processed": fixtures_processed,
        "drift_detected_count": drift_detected_count,
        "summary": summary,
    }
    log.info("canary.done", extra=result)
    return result
