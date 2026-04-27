"""Tests for self-consistency check in agent_narrator.

Isolates the _self_consistency_check and _has_critical_findings helpers by
mocking the Strands agent callable.  Three scenarios:
  (a) all 3 runs agree         → self_consistency_passed=True
  (b) 3rd run disagrees        → self_consistency_passed=False
  (c) no CRITICAL in summary   → extra runs never fire, default True
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.shared.models import NarrativeReport, NarrativeFindingRef, ThemeCluster


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(finding_ids: list[str], ism_citations: list[str]) -> NarrativeReport:
    """Build a NarrativeReport with the given finding refs."""
    narratives = [
        NarrativeFindingRef(
            finding_id=fid,
            group_theme=None,
            remediation="Revoke access immediately.",
            ism_citation=ism,
        )
        for fid, ism in zip(finding_ids, ism_citations)
    ]
    return NarrativeReport(
        run_id="run_sc",
        executive_summary="Critical findings detected.",
        theme_clusters=[],
        finding_narratives=narratives,
        cycle_over_cycle=None,
        total_findings=len(finding_ids),
        model_id="claude-sonnet-4-6",
        generated_at=datetime(2026, 4, 25, 9, 0, 0),
    )


def _make_report_no_findings() -> NarrativeReport:
    return NarrativeReport(
        run_id="run_sc",
        executive_summary="No findings this cycle.",
        theme_clusters=[],
        finding_narratives=[],
        cycle_over_cycle=None,
        total_findings=0,
        model_id="claude-sonnet-4-6",
        generated_at=datetime(2026, 4, 25, 9, 0, 0),
    )


def _agent_result(report: NarrativeReport) -> MagicMock:
    res = MagicMock()
    res.structured_output = report
    return res


# ---------------------------------------------------------------------------
# Import helpers under test (after mocking BedrockModel at module import time)
# ---------------------------------------------------------------------------


def _import_helpers():
    """Import the private helpers; re-import each call to pick up fresh state."""
    from src.agent_narrator import handler as h
    return h._self_consistency_check, h._has_critical_findings


# ---------------------------------------------------------------------------
# Test (a): all 3 runs agree → consistent
# ---------------------------------------------------------------------------


@mock_aws
def test_all_three_runs_agree_returns_true():
    """When all three agent runs cite the same finding/ISM set, consistent=True."""
    report_a = _make_report(["F-1", "F-2"], ["ISM-1546", "ISM-1557"])

    # agent is called twice more in _self_consistency_check
    extra_results = [_agent_result(report_a), _agent_result(report_a)]
    extra_agent = MagicMock(side_effect=extra_results)

    from src.agent_narrator import handler as h

    with patch("src.agent_narrator.handler.BedrockModel", MagicMock()), \
         patch("src.agent_narrator.handler.Agent", return_value=extra_agent):
        result = h._self_consistency_check("prompt text", report_a)

    assert result is True


@mock_aws
def test_third_run_disagrees_returns_false():
    """When the 3rd agent run cites a different finding set, consistent=False."""
    report_a = _make_report(["F-1", "F-2"], ["ISM-1546", "ISM-1557"])
    report_different = _make_report(["F-1", "F-3"], ["ISM-1546", "ISM-0000"])

    # first extra call matches, second extra call diverges
    extra_results = [_agent_result(report_a), _agent_result(report_different)]
    extra_agent = MagicMock(side_effect=extra_results)

    from src.agent_narrator import handler as h

    with patch("src.agent_narrator.handler.BedrockModel", MagicMock()), \
         patch("src.agent_narrator.handler.Agent", return_value=extra_agent):
        result = h._self_consistency_check("prompt text", report_a)

    assert result is False


@mock_aws
def test_second_extra_run_fails_gracefully_returns_true():
    """Transient Bedrock failure in extra run → defaults to True (don't break primary path)."""
    report_a = _make_report(["F-1"], ["ISM-1546"])

    extra_results = [_agent_result(report_a), Exception("Bedrock throttle")]

    def _side_effect(*args, **kwargs):
        val = extra_results.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    extra_agent = MagicMock(side_effect=_side_effect)

    from src.agent_narrator import handler as h

    with patch("src.agent_narrator.handler.BedrockModel", MagicMock()), \
         patch("src.agent_narrator.handler.Agent", return_value=extra_agent):
        result = h._self_consistency_check("prompt text", report_a)

    assert result is True


# ---------------------------------------------------------------------------
# Test (c): no CRITICAL findings → extra runs never fire, default True
# ---------------------------------------------------------------------------


@mock_aws
def test_no_critical_findings_no_extra_runs():
    """With no CRITICAL findings in summary, handler skips self-consistency entirely."""
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-456",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    report = _make_report_no_findings()
    primary_result = _agent_result(report)
    primary_agent = MagicMock(return_value=primary_result)

    # _self_consistency_check must NOT be called
    with patch("src.agent_narrator.handler._build_agent", return_value=primary_agent), \
         patch("src.agent_narrator.handler._self_consistency_check") as mock_sc:
        from src.agent_narrator.handler import lambda_handler
        result = lambda_handler(
            {
                "run_id": "run_sc",
                "bucket": "test-bucket-456",
                "summary": {"R1": 0, "CRITICAL": 0},
                "finding_ids": [],
            },
            None,
        )

    mock_sc.assert_not_called()
    # Retrieve written narrative and confirm self_consistency_passed defaults True
    body = s3.get_object(Bucket="test-bucket-456", Key="narratives/run_sc/narrative.json")["Body"].read()
    data = json.loads(body)
    assert data.get("self_consistency_passed", True) is True


@mock_aws
def test_critical_findings_trigger_self_consistency_check():
    """With CRITICAL findings in summary, handler calls _self_consistency_check."""
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-789",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    report = _make_report(["F-1"], ["ISM-1546"])
    primary_result = _agent_result(report)
    primary_agent = MagicMock(return_value=primary_result)

    with patch("src.agent_narrator.handler._build_agent", return_value=primary_agent), \
         patch("src.agent_narrator.handler._self_consistency_check", return_value=True) as mock_sc:
        from src.agent_narrator.handler import lambda_handler
        lambda_handler(
            {
                "run_id": "run_sc",
                "bucket": "test-bucket-789",
                "summary": {"R1": 1, "CRITICAL": 1},
                "finding_ids": ["F-1"],
            },
            None,
        )

    mock_sc.assert_called_once()


@mock_aws
def test_self_consistency_false_sets_flag_in_narrative():
    """When _self_consistency_check returns False, narrative has self_consistency_passed=False."""
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-abc",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )

    report = _make_report(["F-1"], ["ISM-1546"])
    primary_result = _agent_result(report)
    primary_agent = MagicMock(return_value=primary_result)

    with patch("src.agent_narrator.handler._build_agent", return_value=primary_agent), \
         patch("src.agent_narrator.handler._self_consistency_check", return_value=False):
        from src.agent_narrator.handler import lambda_handler
        lambda_handler(
            {
                "run_id": "run_sc",
                "bucket": "test-bucket-abc",
                "summary": {"R1": 1, "CRITICAL": 1},
                "finding_ids": ["F-1"],
            },
            None,
        )

    body = s3.get_object(Bucket="test-bucket-abc", Key="narratives/run_sc/narrative.json")["Body"].read()
    data = json.loads(body)
    assert data["self_consistency_passed"] is False
