"""Tests for drift_detector Lambda handler — weekly KS drift detection."""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

RUNS_TABLE = "test-runs-table-123"
DRIFT_SIGNALS_TABLE = "test-drift-signals-789"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_run_item(
    run_id: str,
    started_at: datetime,
    faithfulness: float,
) -> dict:
    """Build a minimal runs-table item with judge_score.faithfulness."""
    item = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "judge_score": {
            "faithfulness": Decimal(str(faithfulness)),
        },
    }
    return item


@pytest.fixture
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNS_TABLE", RUNS_TABLE)
    monkeypatch.setenv("DRIFT_SIGNALS_TABLE", DRIFT_SIGNALS_TABLE)
    monkeypatch.setenv("DRIFT_ALPHA", "0.05")


def _create_tables(ddb):
    """Create both DDB tables needed by the handler."""
    runs = ddb.create_table(
        TableName=RUNS_TABLE,
        KeySchema=[{"AttributeName": "run_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "run_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    runs.wait_until_exists()

    drift = ddb.create_table(
        TableName=DRIFT_SIGNALS_TABLE,
        KeySchema=[{"AttributeName": "signal_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "signal_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    drift.wait_until_exists()
    return runs, drift


# ---------------------------------------------------------------------------
# test_no_drift_no_signal_written
# ---------------------------------------------------------------------------


@mock_aws
def test_no_drift_no_signal_written(_env: None) -> None:
    """Both windows have similar faithfulness (0.9) → KS test finds no drift → no signal."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    runs_table, drift_table = _create_tables(ddb)

    now = _utcnow()
    # Seed recent window (0–7 days ago): 10 runs at faithfulness=0.9
    for i in range(10):
        ts = now - timedelta(days=i % 7, hours=i)
        runs_table.put_item(Item=_make_run_item(f"recent-{i}", ts, 0.9))

    # Seed baseline window (7–37 days ago): 10 runs at same faithfulness=0.9
    for i in range(10):
        ts = now - timedelta(days=10 + i)
        runs_table.put_item(Item=_make_run_item(f"baseline-{i}", ts, 0.9))

    with patch("boto3.resource", return_value=ddb):
        from src.drift_detector import handler
        importlib.reload(handler)

        result = handler.lambda_handler({}, None)

    assert result["drift_detected"] is False
    assert result["statistic"] == pytest.approx(0.0)

    # No signal should be written
    scan = drift_table.scan()
    assert len(scan["Items"]) == 0


# ---------------------------------------------------------------------------
# test_drift_detected_writes_signal
# ---------------------------------------------------------------------------


@mock_aws
def test_drift_detected_writes_signal(_env: None) -> None:
    """Recent window faithfulness drops to ~0.5 vs baseline 0.9 → KS detects drift → signal written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    runs_table, drift_table = _create_tables(ddb)

    now = _utcnow()
    # Seed recent window: 20 runs at faithfulness=0.5 (sharp drop)
    for i in range(20):
        ts = now - timedelta(days=i % 6, hours=i)
        runs_table.put_item(Item=_make_run_item(f"recent-{i}", ts, 0.5))

    # Seed baseline window: 20 runs at faithfulness=0.9
    for i in range(20):
        ts = now - timedelta(days=10 + i)
        runs_table.put_item(Item=_make_run_item(f"baseline-{i}", ts, 0.9))

    with patch("boto3.resource", return_value=ddb):
        from src.drift_detector import handler
        importlib.reload(handler)

        result = handler.lambda_handler({}, None)

    assert result["drift_detected"] is True
    assert result["statistic"] > 0.0
    assert result["pvalue"] < 0.05

    # One drift signal must be written
    scan = drift_table.scan()
    assert len(scan["Items"]) == 1
    item = scan["Items"][0]
    assert item["signal_type"] == "ks_drift"
    assert item["metric_name"] == "faithfulness"
    assert item["signal_id"].startswith("ks_")
    assert float(item["delta"]) > 0.0  # KS statistic stored in delta
    assert "details" in item
    details = item["details"]
    assert "statistic" in details
    assert "pvalue" in details
    assert int(details["n_recent"]) == 20
    assert int(details["n_baseline"]) == 20


# ---------------------------------------------------------------------------
# test_no_runs_in_recent_window_returns_gracefully
# ---------------------------------------------------------------------------


@mock_aws
def test_no_runs_in_recent_window_returns_gracefully(_env: None) -> None:
    """Empty recent window → KS returns no drift (insufficient samples) → no signal written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    runs_table, drift_table = _create_tables(ddb)

    now = _utcnow()
    # Only seed baseline; recent window is empty
    for i in range(10):
        ts = now - timedelta(days=10 + i)
        runs_table.put_item(Item=_make_run_item(f"baseline-{i}", ts, 0.9))

    with patch("boto3.resource", return_value=ddb):
        from src.drift_detector import handler
        importlib.reload(handler)

        result = handler.lambda_handler({}, None)

    # Insufficient samples — no drift, no signal, no exception
    assert result["drift_detected"] is False

    scan = drift_table.scan()
    assert len(scan["Items"]) == 0
