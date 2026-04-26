"""Tests for shadow_eval Lambda — DDB stream-triggered re-judge + drift detection."""
from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "test-drift-signals-456"
JUDGE_FN = "arn:aws:lambda:ap-southeast-2:123456789012:function:judge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_insert_record(
    run_id: str = "run-abc123",
    narrative_uri: str = "s3://test-bucket-123/narrative.json",
    findings_uri: str = "s3://test-bucket-123/findings.json",
    old_faithfulness: float = 0.95,
) -> dict:
    """Build a minimal DDB Streams INSERT record with NewImage in wire format."""
    return {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                "run_id": {"S": run_id},
                "narrative_s3_uri": {"S": narrative_uri},
                "findings_s3_uri": {"S": findings_uri},
                "judge_score": {
                    "M": {
                        "faithfulness": {"N": str(old_faithfulness)},
                    }
                },
            }
        },
    }


def _make_non_insert_record(event_name: str = "MODIFY") -> dict:
    return {
        "eventName": event_name,
        "dynamodb": {
            "NewImage": {
                "run_id": {"S": "run-modify-001"},
                "narrative_s3_uri": {"S": "s3://test-bucket-123/narrative.json"},
                "findings_s3_uri": {"S": "s3://test-bucket-123/findings.json"},
                "judge_score": {"M": {"faithfulness": {"N": "0.95"}}},
            }
        },
    }


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("DRIFT_SIGNALS_TABLE", TABLE_NAME)
    monkeypatch.setenv("JUDGE_FUNCTION_NAME", JUDGE_FN)
    monkeypatch.setenv("SHADOW_DRIFT_THRESHOLD", "0.10")


def _create_drift_table(ddb):
    table = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "signal_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "signal_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@mock_aws
def test_skip_non_insert_events(_env):
    """MODIFY / REMOVE events must be silently skipped — no signals written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_drift_table(ddb)

    mock_lambda_client = MagicMock()

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        event = {
            "Records": [
                _make_non_insert_record("MODIFY"),
                _make_non_insert_record("REMOVE"),
            ]
        }
        result = handler.lambda_handler(event, None)

    assert result["records_processed"] == 2
    assert result["signals_written"] == 0
    # Lambda invoke must NOT have been called since we skip non-INSERT records
    mock_lambda_client.invoke.assert_not_called()


@mock_aws
def test_skip_runs_missing_s3_uris(_env):
    """INSERT events without narrative_s3_uri or findings_s3_uri are skipped."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_drift_table(ddb)

    mock_lambda_client = MagicMock()

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        incomplete_record = {
            "eventName": "INSERT",
            "dynamodb": {
                "NewImage": {
                    "run_id": {"S": "run-no-uris"},
                    # Missing narrative_s3_uri and findings_s3_uri
                    "judge_score": {"M": {"faithfulness": {"N": "0.95"}}},
                }
            },
        }
        result = handler.lambda_handler({"Records": [incomplete_record]}, None)

    assert result["records_processed"] == 1
    assert result["signals_written"] == 0
    mock_lambda_client.invoke.assert_not_called()


@mock_aws
def test_drift_above_threshold_writes_signal(_env):
    """old=0.95, new=0.80, abs(delta)=0.15 > 0.10 → drift signal written to DDB."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_drift_table(ddb)

    judge_payload = json.dumps(
        {"faithfulness": 0.80, "completeness": 0.90, "fabrication": 0.0}
    ).encode()
    mock_response_payload = MagicMock()
    mock_response_payload.read.return_value = judge_payload
    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.return_value = {"Payload": mock_response_payload}

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        record = _make_insert_record(run_id="run-drift-high", old_faithfulness=0.95)
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["signals_written"] == 1

    # Verify a drift signal row was written to DDB
    scan = table.scan()
    assert len(scan["Items"]) == 1
    item = scan["Items"][0]
    assert item["signal_type"] == "shadow_drift"
    assert item["metric_name"] == "faithfulness"
    assert "signal_id" in item
    assert item["signal_id"].startswith("shadow_run-drift-high_")
    # delta should be approximately -0.15
    assert abs(float(item["delta"]) + 0.15) < 0.001
    assert "details" in item
    assert float(item["details"]["old_faithfulness"]) == pytest.approx(0.95)
    assert float(item["details"]["new_faithfulness"]) == pytest.approx(0.80)


@mock_aws
def test_drift_below_threshold_does_not_write(_env):
    """old=0.95, new=0.90, abs(delta)=0.05 < 0.10 → no drift signal written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_drift_table(ddb)

    judge_payload = json.dumps({"faithfulness": 0.90}).encode()
    mock_response_payload = MagicMock()
    mock_response_payload.read.return_value = judge_payload
    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.return_value = {"Payload": mock_response_payload}

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        record = _make_insert_record(run_id="run-drift-low", old_faithfulness=0.95)
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["signals_written"] == 0

    scan = table.scan()
    assert len(scan["Items"]) == 0


@mock_aws
def test_judge_invocation_failure_skips_run(_env):
    """When Lambda.invoke() raises an exception, the run is skipped gracefully."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_drift_table(ddb)

    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.side_effect = Exception("Connection timeout")

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        record = _make_insert_record(run_id="run-invoke-fail", old_faithfulness=0.95)
        # Must NOT raise — failure is handled internally
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["signals_written"] == 0

    scan = table.scan()
    assert len(scan["Items"]) == 0


@mock_aws
def test_multiple_records_mixed_events(_env):
    """Batch with INSERT (drift) + MODIFY (skip) + INSERT (no drift) → 1 signal."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_drift_table(ddb)

    call_count = 0

    def fake_invoke(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call: new=0.80 (drift). Second call: new=0.92 (no drift).
        new_score = 0.80 if call_count == 1 else 0.92
        payload_bytes = json.dumps({"faithfulness": new_score}).encode()
        mock_payload = MagicMock()
        mock_payload.read.return_value = payload_bytes
        return {"Payload": mock_payload}

    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.side_effect = fake_invoke

    with (
        patch("boto3.client", return_value=mock_lambda_client),
        patch("boto3.resource", return_value=ddb),
    ):
        from src.shadow_eval import handler
        importlib.reload(handler)

        event = {
            "Records": [
                _make_insert_record(run_id="run-batch-1", old_faithfulness=0.95),
                _make_non_insert_record("MODIFY"),
                _make_insert_record(run_id="run-batch-2", old_faithfulness=0.95),
            ]
        }
        result = handler.lambda_handler(event, None)

    assert result["records_processed"] == 3
    assert result["signals_written"] == 1

    scan = table.scan()
    assert len(scan["Items"]) == 1
    assert scan["Items"][0]["signal_id"].startswith("shadow_run-batch-1_")
