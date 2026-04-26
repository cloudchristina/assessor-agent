"""Tests for canary_orchestrator Lambda handler.

Mocks S3, SFN, and DDB (moto). All tests follow the established project pattern:
- @mock_aws wraps the whole test
- monkeypatch injects required env vars
- imports are deferred inside tests so moto intercepts boto3 at construction time
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_BASELINES_DIR = str(Path(__file__).resolve().parent.parent.parent / "evals/canary/baselines")
_BUCKET = "test-canary-input-bucket-123"
_CANARY_TABLE = "test-canary-results-123"
_RUNS_TABLE = "test-runs-123"
_SFN_ARN = "arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sfn"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _setup_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Inject required env vars for the handler."""
    monkeypatch.setenv("STATE_MACHINE_ARN", _SFN_ARN)
    monkeypatch.setenv("CANARY_RESULTS_TABLE", _CANARY_TABLE)
    monkeypatch.setenv("RUNS_TABLE", _RUNS_TABLE)
    monkeypatch.setenv("SYNTHETIC_INPUT_BUCKET", _BUCKET)
    monkeypatch.setenv("CANARY_BASELINES_DIR", _BASELINES_DIR)


def _create_canary_table(ddb):  # type: ignore[no-untyped-def]
    """Create the canary_results DDB table."""
    table = ddb.create_table(
        TableName=_CANARY_TABLE,
        KeySchema=[
            {"AttributeName": "canary_run_id", "KeyType": "HASH"},
            {"AttributeName": "month", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "canary_run_id", "AttributeType": "S"},
            {"AttributeName": "month", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def _create_runs_table(ddb):  # type: ignore[no-untyped-def]
    """Create the runs DDB table."""
    table = ddb.create_table(
        TableName=_RUNS_TABLE,
        KeySchema=[
            {"AttributeName": "run_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "run_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def _seed_run_record(
    ddb,  # type: ignore[no-untyped-def]
    run_id: str,
    faithfulness: float = 0.95,
    completeness: float = 0.92,
    findings_count: int = 3,
) -> None:
    """Insert a fake run record that the handler reads after SFN completes."""
    table = ddb.Table(_RUNS_TABLE)
    table.put_item(Item={
        "run_id": run_id,
        "cadence": "weekly",
        "status": "succeeded",
        "findings_count": Decimal(str(findings_count)),
        "judge_score": {
            "faithfulness": Decimal(str(faithfulness)),
            "completeness": Decimal(str(completeness)),
        },
    })


def _make_sfn_stub(run_ids: list[str]) -> MagicMock:
    """Return a MagicMock SFN client that cycles through run_ids on each call."""
    sfn_mock = MagicMock()
    call_index = {"i": 0}

    def _start(**kwargs):  # type: ignore[no-untyped-def]
        idx = call_index["i"]
        call_index["i"] += 1
        rid = run_ids[idx]
        sfn_mock._last_run_id = rid
        return {"executionArn": f"{_SFN_ARN}:{rid}", "startDate": "2026-04-26T00:00:00Z"}

    def _describe(**kwargs):  # type: ignore[no-untyped-def]
        return {"status": "SUCCEEDED", "output": json.dumps({"run_id": sfn_mock._last_run_id})}

    sfn_mock.start_execution.side_effect = _start
    sfn_mock.describe_execution.side_effect = _describe
    return sfn_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@mock_aws
def test_canary_runs_three_fixtures(monkeypatch):
    """Handler processes all 3 baseline fixtures without raising."""
    _setup_env(monkeypatch)

    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_canary_table(ddb)
    _create_runs_table(ddb)

    boto3.client("s3", region_name="ap-southeast-2").create_bucket(
        Bucket=_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    run_ids = ["canary-2025-11-aaa", "canary-2025-12-bbb", "canary-2026-01-ccc"]
    for rid in run_ids:
        _seed_run_record(ddb, rid)

    sfn_stub = _make_sfn_stub(run_ids)

    import importlib

    import src.canary_orchestrator.handler as mod
    importlib.reload(mod)

    with patch.object(mod, "sfn", sfn_stub):
        result = mod.lambda_handler({}, None)

    assert result["fixtures_processed"] == 3
    assert "drift_detected_count" in result
    assert isinstance(result["drift_detected_count"], int)


@mock_aws
def test_canary_writes_one_result_per_fixture(monkeypatch):
    """Handler writes exactly one canary_results row per fixture (3 total)."""
    _setup_env(monkeypatch)

    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_canary_table(ddb)
    _create_runs_table(ddb)

    boto3.client("s3", region_name="ap-southeast-2").create_bucket(
        Bucket=_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    run_ids = ["canary-2025-11-x1", "canary-2025-12-x2", "canary-2026-01-x3"]
    for rid in run_ids:
        _seed_run_record(ddb, rid)

    sfn_stub = _make_sfn_stub(run_ids)

    import importlib

    import src.canary_orchestrator.handler as mod
    importlib.reload(mod)

    with patch.object(mod, "sfn", sfn_stub):
        mod.lambda_handler({}, None)

    table = ddb.Table(_CANARY_TABLE)
    items = table.scan()["Items"]
    assert len(items) == 3, f"Expected 3 canary_results rows, got {len(items)}"

    months = {item["month"] for item in items}
    assert "2025-11" in months
    assert "2025-12" in months
    assert "2026-01" in months

    for item in items:
        assert "actual_metrics" in item
        assert "baseline_metrics" in item
        assert "drift_detected" in item
        assert "canary_run_id" in item


@mock_aws
def test_canary_emits_drift_signal_on_threshold_breach(monkeypatch):
    """When actual judge_faithfulness < baseline - tolerance, drift_detected=True."""
    _setup_env(monkeypatch)

    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_canary_table(ddb)
    _create_runs_table(ddb)

    boto3.client("s3", region_name="ap-southeast-2").create_bucket(
        Bucket=_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    # 2025-11: faithfulness=0.50 (well below baseline 0.90 - tolerance 0.05 = 0.85)
    _seed_run_record(ddb, "canary-2025-11-bad", faithfulness=0.50, completeness=0.50)
    # other months: good scores, no drift
    _seed_run_record(ddb, "canary-2025-12-ok", faithfulness=0.95, completeness=0.92)
    _seed_run_record(ddb, "canary-2026-01-ok", faithfulness=0.95, completeness=0.92)

    run_ids = ["canary-2025-11-bad", "canary-2025-12-ok", "canary-2026-01-ok"]
    sfn_stub = _make_sfn_stub(run_ids)

    import importlib

    import src.canary_orchestrator.handler as mod
    importlib.reload(mod)

    with patch.object(mod, "sfn", sfn_stub):
        result = mod.lambda_handler({}, None)

    # At least the 2025-11 fixture drifts
    assert result["drift_detected_count"] >= 1

    items = {item["month"]: item for item in ddb.Table(_CANARY_TABLE).scan()["Items"]}
    nov_item = items.get("2025-11")
    assert nov_item is not None, "No canary_results row for 2025-11"
    assert nov_item["drift_detected"] is True, (
        f"Expected drift_detected=True for 2025-11, got {nov_item.get('drift_detected')}"
    )
    assert "drift_details" in nov_item, "Missing drift_details in canary row"
    # Verify drift_details contains the breached metric
    drift_details = nov_item["drift_details"]
    assert "judge_faithfulness" in drift_details


# ---------------------------------------------------------------------------
# Baseline-generation script smoke test
# ---------------------------------------------------------------------------


def test_generate_canary_baseline_produces_valid_json(tmp_path):
    """Running generate_canary_baseline on a fixture produces a valid baseline JSON."""
    import subprocess

    _repo_root = Path(__file__).resolve().parent.parent.parent
    fixture = _repo_root / "evals/canary/fixtures/month_2025-11.csv"
    out = tmp_path / "baseline.json"

    result = subprocess.run(
        [
            str(_repo_root / ".venv/bin/python"),
            "scripts/generate_canary_baseline.py",
            "--fixture", str(fixture),
            "--out", str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(_repo_root),
    )
    assert result.returncode == 0, (
        f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert out.exists(), "Output file was not created"

    data = json.loads(out.read_text())
    assert data["month"] == "2025-11"
    assert "expected_metrics" in data
    assert "total_findings" in data["expected_metrics"]
    assert "per_rule_counts" in data["expected_metrics"]
    assert data["expected_metrics"]["total_findings"] == 3
    assert "tolerance" in data
    assert "notes" in data
