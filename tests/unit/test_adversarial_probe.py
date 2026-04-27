"""Unit tests for adversarial_probe Lambda handler.

Mocks:
  - boto3 S3 via moto
  - Strands Agent via patch on _build_agent
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.shared.models import WeakClaim, WeakClaimsReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(weak_claims: list[WeakClaim]) -> WeakClaimsReport:
    return WeakClaimsReport(
        weak_claims=weak_claims,
        overall_assessment="test assessment",
        model_id="claude-haiku-4-5",
    )


def _agent_result(report: WeakClaimsReport) -> MagicMock:
    """Mimic strands.AgentResult — only the attribute we use."""
    res = MagicMock()
    res.structured_output = report
    return res


def _setup_s3() -> None:
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-probe",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(
        Bucket="test-bucket-probe",
        Key="findings.json",
        Body=json.dumps({"findings": [{"finding_id": "F-1", "severity": "HIGH"}]}).encode(),
    )
    s3.put_object(
        Bucket="test-bucket-probe",
        Key="narrative.json",
        Body=json.dumps({"total_findings": 1, "executive_summary": "One high finding."}).encode(),
    )


def _event() -> dict:
    return {
        "narrative_s3_uri": "s3://test-bucket-probe/narrative.json",
        "findings_s3_uri": "s3://test-bucket-probe/findings.json",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@mock_aws
def test_passed_when_no_weak_claims():
    """Empty weak_claims list → max confidence defaults to 0.0 → passed=True."""
    _setup_s3()
    report = _make_report([])
    fake_agent = MagicMock(return_value=_agent_result(report))
    with patch("src.adversarial_probe.handler._build_agent", return_value=fake_agent):
        from src.adversarial_probe.handler import lambda_handler

        out = lambda_handler(_event(), None)
    assert out["passed"] is True
    assert out["passed_int"] == 1
    assert out["weak_claims"] == []


@mock_aws
def test_passed_when_max_confidence_at_threshold():
    """Confidence exactly 0.7 → boundary condition → passed=True."""
    _setup_s3()
    report = _make_report(
        [WeakClaim(claim="borderline claim", confidence=0.7, reasoning="at threshold")]
    )
    fake_agent = MagicMock(return_value=_agent_result(report))
    with patch("src.adversarial_probe.handler._build_agent", return_value=fake_agent):
        from src.adversarial_probe.handler import lambda_handler

        out = lambda_handler(_event(), None)
    assert out["passed"] is True
    assert out["passed_int"] == 1


@mock_aws
def test_failed_when_max_confidence_above_threshold():
    """Confidence 0.71 → strictly above threshold → passed=False."""
    _setup_s3()
    report = _make_report(
        [WeakClaim(claim="suspicious claim", confidence=0.71, reasoning="above threshold")]
    )
    fake_agent = MagicMock(return_value=_agent_result(report))
    with patch("src.adversarial_probe.handler._build_agent", return_value=fake_agent):
        from src.adversarial_probe.handler import lambda_handler

        out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert out["passed_int"] == 0


@mock_aws
def test_returns_correct_payload_shape():
    """Return dict must contain exactly the keys: passed, passed_int, weak_claims."""
    _setup_s3()
    report = _make_report([])
    fake_agent = MagicMock(return_value=_agent_result(report))
    with patch("src.adversarial_probe.handler._build_agent", return_value=fake_agent):
        from src.adversarial_probe.handler import lambda_handler

        out = lambda_handler(_event(), None)
    assert set(out.keys()) == {"passed", "passed_int", "weak_claims"}


@mock_aws
def test_structured_output_model_passed_to_agent():
    """Agent must be called with structured_output_model=WeakClaimsReport."""
    _setup_s3()
    report = _make_report([])
    fake_agent = MagicMock(return_value=_agent_result(report))
    with patch("src.adversarial_probe.handler._build_agent", return_value=fake_agent):
        from src.adversarial_probe.handler import lambda_handler

        lambda_handler(_event(), None)
    fake_agent.assert_called_once()
    assert fake_agent.call_args.kwargs.get("structured_output_model") is WeakClaimsReport
