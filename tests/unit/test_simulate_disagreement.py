"""Tests for scripts/simulate_disagreement.py CLI."""
from __future__ import annotations

import sys

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def _env(monkeypatch):
    """Set up environment with findings table name."""
    monkeypatch.setenv("FINDINGS_TABLE", "findings")


@mock_aws
def test_simulate_disagreement_updates_finding(_env, monkeypatch, capsys):
    """Test that simulate_disagreement updates a finding in DDB."""
    from scripts.simulate_disagreement import main

    # Create the findings table
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    ddb.create_table(
        TableName="findings",
        KeySchema=[
            {"AttributeName": "run_id", "KeyType": "HASH"},
            {"AttributeName": "finding_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "run_id", "AttributeType": "S"},
            {"AttributeName": "finding_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()

    # Pre-seed a finding
    table = ddb.Table("findings")
    table.put_item(
        Item={
            "run_id": "run_test_123",
            "finding_id": "finding_abc456",
            "rule_id": "R1",
            "severity": "CRITICAL",
        }
    )

    # Call main() with simulated args
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts.simulate_disagreement",
            "--run-id=run_test_123",
            "--finding-id=finding_abc456",
            "--decision=false_positive",
            "--reviewer-sub=test-reviewer",
            "--rationale=test override",
        ],
    )

    result = main()
    assert result == 0

    # Verify the finding was updated
    response = table.get_item(Key={"run_id": "run_test_123", "finding_id": "finding_abc456"})
    item = response["Item"]
    assert item["decision"] == "false_positive"
    assert item["reviewer_sub"] == "test-reviewer"
    assert item["rationale"] == "test override"
    assert "decided_at" in item

    # Verify output
    captured = capsys.readouterr()
    assert "updated finding finding_abc456" in captured.out
    assert "decision: false_positive" in captured.out
    assert "reviewer: test-reviewer" in captured.out


@mock_aws
def test_simulate_disagreement_missing_findings_table(_env, monkeypatch, capsys, tmp_path):
    """Test error handling when FINDINGS_TABLE is not set."""
    from scripts.simulate_disagreement import main

    # Clear the env var
    monkeypatch.delenv("FINDINGS_TABLE", raising=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts.simulate_disagreement",
            "--run-id=run_test",
            "--finding-id=finding_test",
            "--decision=confirmed_risk",
        ],
    )

    result = main()
    assert result == 2

    captured = capsys.readouterr()
    assert "error: --findings-table is required" in captured.err


@mock_aws
def test_simulate_disagreement_all_decision_types(_env, monkeypatch, capsys):
    """Test that all decision types are accepted."""
    from scripts.simulate_disagreement import main

    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    ddb.create_table(
        TableName="findings",
        KeySchema=[
            {"AttributeName": "run_id", "KeyType": "HASH"},
            {"AttributeName": "finding_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "run_id", "AttributeType": "S"},
            {"AttributeName": "finding_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()

    table = ddb.Table("findings")

    decisions = ["confirmed_risk", "false_positive", "accepted_exception", "escalated"]

    for i, decision in enumerate(decisions):
        finding_id = f"finding_{i}"
        table.put_item(Item={"run_id": "run_test", "finding_id": finding_id})

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts.simulate_disagreement",
                "--run-id=run_test",
                f"--finding-id={finding_id}",
                f"--decision={decision}",
            ],
        )

        result = main()
        assert result == 0

        response = table.get_item(Key={"run_id": "run_test", "finding_id": finding_id})
        assert response["Item"]["decision"] == decision
