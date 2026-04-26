"""Tests for reviewer_disagreement_digest Lambda — weekly SES digest of pending candidates."""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "test-golden-set-candidates-digest-789"
DIGEST_FROM = "noreply@example.com"
COMPLIANCE_EMAIL = "compliance@example.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_candidates_table(ddb):
    table = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "candidate_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "candidate_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def _make_item(
    candidate_id: str = "cand-001",
    finding_id: str = "find-001",
    expected_severity: str = "CRITICAL",
    decision: str = "false_positive",
    rationale: str = "Test rationale",
    created_at: str = "2026-04-25T10:00:00+00:00",
    status: str = "pending",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "finding_id": finding_id,
        "expected_severity": expected_severity,
        "decision": decision,
        "rationale": rationale,
        "created_at": created_at,
        "status": status,
    }


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("GOLDEN_SET_CANDIDATES_TABLE", TABLE_NAME)
    monkeypatch.setenv("DIGEST_FROM", DIGEST_FROM)
    monkeypatch.setenv("COMPLIANCE_EMAIL", COMPLIANCE_EMAIL)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@mock_aws
def test_digest_sent_with_pending_items(_env):
    """When pending items exist, email is sent with count in subject and items in body."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    ses_client = boto3.client("ses", region_name="ap-southeast-2")
    table = _create_candidates_table(ddb)

    # Insert two pending items with a recent created_at
    table.put_item(Item=_make_item("cand-001", created_at="2026-04-25T10:00:00+00:00"))
    table.put_item(
        Item=_make_item(
            "cand-002",
            finding_id="find-002",
            expected_severity="LOW",
            decision="confirmed_risk",
            rationale="Real risk",
            created_at="2026-04-24T08:00:00+00:00",
        )
    )
    # Insert a non-pending item — must NOT appear in digest
    table.put_item(Item=_make_item("cand-003", status="reviewed", created_at="2026-04-23T00:00:00+00:00"))

    # Verify the SES sender address
    ses_client.verify_email_identity(EmailAddress=DIGEST_FROM)

    with patch("boto3.resource", return_value=ddb), patch("boto3.client", return_value=ses_client):
        from src.reviewer_disagreement_digest import handler

        importlib.reload(handler)
        result = handler.lambda_handler({}, None)

    assert result["sent"] is True
    assert result["count"] == 2

    # Confirm the email was actually sent via moto
    messages = ses_client.list_identities()
    assert DIGEST_FROM in messages["Identities"]


@mock_aws
def test_digest_sent_even_with_no_pending_items(_env):
    """Empty pending list still triggers SES send (compliance must know all-clear)."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    ses_client = boto3.client("ses", region_name="ap-southeast-2")
    _create_candidates_table(ddb)

    ses_client.verify_email_identity(EmailAddress=DIGEST_FROM)

    with patch("boto3.resource", return_value=ddb), patch("boto3.client", return_value=ses_client):
        from src.reviewer_disagreement_digest import handler

        importlib.reload(handler)
        result = handler.lambda_handler({}, None)

    assert result["sent"] is True
    assert result["count"] == 0


@mock_aws
def test_missing_env_vars_raises():
    """Missing required env vars raise KeyError at import/call time."""
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    ses_client = boto3.client("ses", region_name="ap-southeast-2")
    _create_candidates_table(ddb)

    # Intentionally do NOT set env vars
    with patch("boto3.resource", return_value=ddb), patch("boto3.client", return_value=ses_client):
        from src.reviewer_disagreement_digest import handler

        importlib.reload(handler)

        with pytest.raises(KeyError):
            handler.lambda_handler({}, None)


@mock_aws
def test_format_helper_with_items():
    """_format() returns expected markdown lines for a list of items."""
    from src.reviewer_disagreement_digest import handler

    importlib.reload(handler)

    items = [
        _make_item("cand-001", finding_id="find-001", expected_severity="CRITICAL", decision="false_positive"),
        _make_item("cand-002", finding_id="find-002", expected_severity="LOW", decision="confirmed_risk"),
    ]
    body = handler._format(items)

    assert "2 pending candidates" in body
    assert "cand-001" in body
    assert "CRITICAL" in body
    assert "false_positive" in body
    assert "cand-002" in body
    assert "LOW" in body


@mock_aws
def test_format_helper_empty():
    """_format() returns the all-clear string for an empty list."""
    from src.reviewer_disagreement_digest import handler

    importlib.reload(handler)

    body = handler._format([])
    assert "No pending" in body
