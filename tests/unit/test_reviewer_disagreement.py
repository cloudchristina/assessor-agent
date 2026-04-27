"""Tests for reviewer_disagreement Lambda — DDB stream-triggered golden-set candidate queue."""
from __future__ import annotations

import importlib
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "test-golden-set-candidates-789"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_modify_record(
    run_id: str = "run-abc123",
    finding_id: str = "find-001",
    rule_id: str = "R1",
    severity: str = "CRITICAL",
    decision: str = "false_positive",
    old_decision: str | None = None,
    reviewer_sub: str = "user-sub-xyz",
    rationale: str = "Reviewed and dismissed.",
) -> dict:
    """Build a minimal DDB Streams MODIFY record with NewImage + OldImage in wire format."""
    new_image: dict = {
        "run_id": {"S": run_id},
        "finding_id": {"S": finding_id},
        "rule_id": {"S": rule_id},
        "severity": {"S": severity},
        "decision": {"S": decision},
        "reviewer_sub": {"S": reviewer_sub},
        "rationale": {"S": rationale},
    }
    old_image: dict = {
        "run_id": {"S": run_id},
        "finding_id": {"S": finding_id},
        "rule_id": {"S": rule_id},
        "severity": {"S": severity},
    }
    if old_decision is not None:
        old_image["decision"] = {"S": old_decision}

    return {
        "eventName": "MODIFY",
        "dynamodb": {
            "NewImage": new_image,
            "OldImage": old_image,
        },
    }


def _make_non_modify_record(event_name: str = "INSERT") -> dict:
    return {
        "eventName": event_name,
        "dynamodb": {
            "NewImage": {
                "run_id": {"S": "run-insert-001"},
                "finding_id": {"S": "find-insert-001"},
                "severity": {"S": "CRITICAL"},
                "decision": {"S": "false_positive"},
            },
            "OldImage": {},
        },
    }


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("GOLDEN_SET_CANDIDATES_TABLE", TABLE_NAME)


def _create_candidates_table(ddb):
    table = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "candidate_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "candidate_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@mock_aws
def test_skip_non_modify_events(_env):
    """INSERT and REMOVE events must be silently skipped — no candidates written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        event = {
            "Records": [
                _make_non_modify_record("INSERT"),
                _make_non_modify_record("REMOVE"),
            ]
        }
        result = handler.lambda_handler(event, None)

    assert result["records_processed"] == 2
    assert result["candidates_written"] == 0
    assert len(table.scan()["Items"]) == 0


@mock_aws
def test_skip_when_decision_unchanged(_env):
    """MODIFY where new.decision == old.decision → no candidate written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        # Same decision in both old and new image
        record = _make_modify_record(
            severity="CRITICAL",
            decision="false_positive",
            old_decision="false_positive",
        )
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["candidates_written"] == 0
    assert len(table.scan()["Items"]) == 0


@mock_aws
def test_skip_when_no_disagreement(_env):
    """CRITICAL + confirmed_risk is NOT a disagreement → no candidate written."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        # CRITICAL + confirmed_risk — triage agrees with severity, not a disagreement
        record = _make_modify_record(
            severity="CRITICAL",
            decision="confirmed_risk",
            old_decision=None,  # first decision
        )
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["candidates_written"] == 0
    assert len(table.scan()["Items"]) == 0


@mock_aws
def test_writes_candidate_on_critical_false_positive(_env):
    """CRITICAL + false_positive → 1 candidate written to golden_set_candidates."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        record = _make_modify_record(
            run_id="run-crit-fp",
            finding_id="find-crit-001",
            rule_id="R2",
            severity="CRITICAL",
            decision="false_positive",
            old_decision=None,
            reviewer_sub="user-alice",
            rationale="Not actually critical.",
        )
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["candidates_written"] == 1

    items = table.scan()["Items"]
    assert len(items) == 1
    item = items[0]
    assert item["candidate_id"].startswith("cand_run-crit-fp_find-crit-001_")
    assert item["status"] == "pending"
    assert item["run_id"] == "run-crit-fp"
    assert item["finding_id"] == "find-crit-001"
    assert item["rule_id"] == "R2"
    assert item["expected_severity"] == "CRITICAL"
    assert item["decision"] == "false_positive"
    assert item["reviewer_sub"] == "user-alice"
    assert item["rationale"] == "Not actually critical."
    assert "created_at" in item


@mock_aws
def test_writes_candidate_on_low_confirmed_risk(_env):
    """LOW + confirmed_risk → 1 candidate written to golden_set_candidates."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        record = _make_modify_record(
            run_id="run-low-cr",
            finding_id="find-low-001",
            rule_id="R4",
            severity="LOW",
            decision="confirmed_risk",
            old_decision=None,
            reviewer_sub="user-bob",
            rationale="Despite LOW, this is a real risk.",
        )
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["candidates_written"] == 1

    items = table.scan()["Items"]
    assert len(items) == 1
    item = items[0]
    assert item["candidate_id"].startswith("cand_run-low-cr_find-low-001_")
    assert item["expected_severity"] == "LOW"
    assert item["decision"] == "confirmed_risk"
    assert item["reviewer_sub"] == "user-bob"


@mock_aws
def test_handles_first_decision(_env):
    """Old image lacks decision, new has decision → counted as a change → candidate written if disagreement."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    with patch("boto3.resource", return_value=ddb):
        from src.reviewer_disagreement import handler
        importlib.reload(handler)

        # old_decision=None means OldImage has no 'decision' key
        record = _make_modify_record(
            run_id="run-first-dec",
            finding_id="find-first-001",
            severity="CRITICAL",
            decision="false_positive",
            old_decision=None,
        )
        result = handler.lambda_handler({"Records": [record]}, None)

    assert result["records_processed"] == 1
    assert result["candidates_written"] == 1

    items = table.scan()["Items"]
    assert len(items) == 1
    assert items[0]["candidate_id"].startswith("cand_run-first-dec_find-first-001_")
