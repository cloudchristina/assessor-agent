"""Tests for eval_harness.ddb_writer — DDB persistence of eval results."""
from __future__ import annotations

import json
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws


TABLE_NAME = "test-eval-results"


def _create_table(ddb):
    """Create the eval_results table with branch_index GSI."""
    table = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "eval_run_id", "KeyType": "HASH"},
            {"AttributeName": "case_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "eval_run_id", "AttributeType": "S"},
            {"AttributeName": "case_id", "AttributeType": "S"},
            {"AttributeName": "branch", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "branch_index",
                "KeySchema": [
                    {"AttributeName": "branch", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("EVAL_RESULTS_TABLE", TABLE_NAME)


@mock_aws
def test_write_eval_result_persists_item(_env):
    """write_eval_result stores all key fields in the DDB table."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    from src.eval_harness.ddb_writer import write_eval_result

    write_eval_result(
        "eval_20260425T1200_abc123",
        "case_001_baseline",
        metrics={"faithfulness": 0.95, "answer_relevance": 0.88},
        branch="main",
        commit_sha="deadbeef",
    )

    table = ddb.Table(TABLE_NAME)
    resp = table.get_item(
        Key={"eval_run_id": "eval_20260425T1200_abc123", "case_id": "case_001_baseline"}
    )
    item = resp["Item"]

    assert item["eval_run_id"] == "eval_20260425T1200_abc123"
    assert item["case_id"] == "case_001_baseline"
    assert item["branch"] == "main"
    assert item["commit_sha"] == "deadbeef"
    assert item["case_type"] == "golden"  # default
    assert "created_at" in item
    assert "metrics" in item


@mock_aws
def test_write_eval_result_handles_float_metrics(_env):
    """Raw Python floats must NOT raise TypeError — they must be stored as Decimal."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    from src.eval_harness.ddb_writer import write_eval_result

    # This must not raise TypeError: Float types are not supported
    write_eval_result(
        "eval_floats_run",
        "case_float_001",
        metrics={
            "faithfulness": 1.0,
            "answer_relevance": 0.873456789,
            "context_precision": 0.5,
            "bertscore_f1": 0.92,
            "rule_precision": {"R1": 1.0, "R2": 0.0},
        },
        branch="main",
        commit_sha="cafebabe",
    )

    table = ddb.Table(TABLE_NAME)
    resp = table.get_item(Key={"eval_run_id": "eval_floats_run", "case_id": "case_float_001"})
    item = resp["Item"]

    # DDB returns numeric values as Decimal — verify they're not raw floats
    metrics = item["metrics"]
    assert isinstance(metrics["faithfulness"], Decimal)
    assert isinstance(metrics["answer_relevance"], Decimal)
    assert isinstance(metrics["bertscore_f1"], Decimal)


@mock_aws
def test_write_eval_result_custom_case_type(_env):
    """case_type='adversarial' is stored when explicitly provided."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    from src.eval_harness.ddb_writer import write_eval_result

    write_eval_result(
        "eval_adv_run",
        "adv_case_001",
        metrics={"faithfulness": 0.5},
        branch="feat/test",
        commit_sha="aabbccdd",
        case_type="adversarial",
    )

    table = ddb.Table(TABLE_NAME)
    resp = table.get_item(Key={"eval_run_id": "eval_adv_run", "case_id": "adv_case_001"})
    assert resp["Item"]["case_type"] == "adversarial"


@mock_aws
def test_load_baseline_for_branch_returns_latest(_env):
    """load_baseline_for_branch returns the newest row (by created_at) for the branch."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    from src.eval_harness.ddb_writer import write_eval_result, load_baseline_for_branch

    # Write an older row first
    write_eval_result(
        "eval_older",
        "case_001",
        metrics={"faithfulness": Decimal("0.70")},
        branch="main",
        commit_sha="oldhash",
    )

    # Write a newer row — use a later timestamp by patching created_at directly
    table = ddb.Table(TABLE_NAME)
    newer_item = {
        "eval_run_id": "eval_newer",
        "case_id": "case_001",
        "branch": "main",
        "commit_sha": "newhash",
        "case_type": "golden",
        "metrics": {"faithfulness": Decimal("0.95")},
        # Use a later ISO timestamp to guarantee sort order
        "created_at": "2099-01-01T00:00:00+00:00",
    }
    table.put_item(Item=newer_item)

    result = load_baseline_for_branch("main")

    assert result is not None
    assert result["eval_run_id"] == "eval_newer"
    assert result["commit_sha"] == "newhash"


@mock_aws
def test_load_baseline_for_branch_returns_none_when_no_baseline(_env):
    """load_baseline_for_branch returns None when no rows exist for the branch."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    from src.eval_harness.ddb_writer import load_baseline_for_branch

    result = load_baseline_for_branch("nonexistent-branch")

    assert result is None


@mock_aws
def test_load_baseline_for_branch_floats_are_deserialised(_env):
    """Values loaded back via load_baseline_for_branch are plain Python floats (JSON-safe)."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _create_table(ddb)

    table = ddb.Table(TABLE_NAME)
    table.put_item(Item={
        "eval_run_id": "eval_deser",
        "case_id": "case_deser",
        "branch": "main",
        "commit_sha": "abc",
        "case_type": "golden",
        "metrics": {"faithfulness": Decimal("0.99")},
        "created_at": "2099-06-01T00:00:00+00:00",
    })

    from src.eval_harness.ddb_writer import load_baseline_for_branch

    result = load_baseline_for_branch("main")

    assert result is not None
    # Decimals must be converted back to float so the result is JSON-serialisable
    assert isinstance(result["metrics"]["faithfulness"], float)
    # Verify it round-trips through JSON without error
    json.dumps(result)  # must not raise
