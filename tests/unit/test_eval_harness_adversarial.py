"""Tests for adversarial case loading, runner, and assertion engine."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.eval_harness.adversarial_runner import (
    AdversarialResult,
    assert_outcome,
    load_all_adversarial_cases,
    run_adversarial_case,
)
from src.shared.models import AdversarialCase


# ---------------------------------------------------------------------------
# Helper — build a minimal AdversarialCase without touching the filesystem
# ---------------------------------------------------------------------------

def _make_case(
    case_id: str = "test-case",
    expected_outcome: str = "judge_pass",
    expected_assertions: list[str] | None = None,
) -> AdversarialCase:
    return AdversarialCase.model_validate(
        {
            "case_id": case_id,
            "description": "unit test case",
            "input_csv": None,
            "generator_fn": None,
            "expected_outcome": expected_outcome,
            "expected_assertions": expected_assertions or ["placeholder"],
        }
    )


# ---------------------------------------------------------------------------
# Existing Task 2.1 test — preserved
# ---------------------------------------------------------------------------


def test_load_all_six_adversarial_cases():
    cases = load_all_adversarial_cases()
    assert len(cases) == 6
    expected_ids = {
        "prompt_injection_row", "empty_findings", "10k_findings",
        "boundary_89d_vs_90d", "duplicate_sid", "evidence_injection",
    }
    assert {c.case_id for c in cases} == expected_ids


# ---------------------------------------------------------------------------
# run_adversarial_case — mocked SFN client
# ---------------------------------------------------------------------------


def _make_sfn_client(status: str = "SUCCEEDED", output: dict | None = None) -> MagicMock:
    """Return a mock boto3 SFN client that returns the given execution status."""
    client = MagicMock()
    client.start_execution.return_value = {"executionArn": "arn:aws:states:ap-southeast-2:123456789012:execution:test-sm:run-001"}
    desc_output = {
        "status": status,
        "output": json.dumps(output or {}),
    }
    client.describe_execution.return_value = desc_output
    return client


def test_run_adversarial_case_succeeded():
    """Mock SFN immediately returns SUCCEEDED with representative output."""
    case = _make_case(expected_outcome="judge_pass")
    sfn = _make_sfn_client(
        status="SUCCEEDED",
        output={
            "__final_state": "PublishTriage",
            "rules": {"total_findings": 3},
            "judge": {"passed": True},
            "narrative": {"text": "Three findings were identified."},
        },
    )

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
    )

    assert result.execution_status == "SUCCEEDED"
    assert result.final_state == "PublishTriage"
    assert result.findings_count == 3
    assert result.judge_passed is True
    assert result.narrative_text == "Three findings were identified."
    assert result.error is None


def test_run_adversarial_case_failed():
    """Mock SFN returns FAILED with an error field."""
    case = _make_case(expected_outcome="rules_engine_error")
    sfn = _make_sfn_client(
        status="FAILED",
        output={},
    )
    sfn.describe_execution.return_value = {
        "status": "FAILED",
        "output": "{}",
        "error": "Lambda.RulesEngineError",
    }

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
    )

    assert result.execution_status == "FAILED"
    assert result.error == "Lambda.RulesEngineError"


def test_run_adversarial_case_no_findings():
    """Mock SFN returns SUCCEEDED with zero findings."""
    case = _make_case(expected_outcome="narrative_no_findings")
    sfn = _make_sfn_client(
        status="SUCCEEDED",
        output={
            "__final_state": "PublishTriage",
            "rules": {"total_findings": 0},
            "judge": {"passed": True},
            "narrative": {"text": "No findings were identified in this review cycle."},
        },
    )

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
    )

    assert result.findings_count == 0
    assert result.execution_status == "SUCCEEDED"


def test_run_adversarial_case_citation_gate_quarantined():
    """Mock SFN returns SUCCEEDED but final_state is MarkQuarantined (citation gate routed there)."""
    case = _make_case(expected_outcome="citation_gate_fail")
    sfn = _make_sfn_client(
        status="SUCCEEDED",
        output={
            "__final_state": "MarkQuarantined",
            "rules": {"total_findings": 2},
            "judge": {"passed": None},
            "narrative": {"text": "Narrative with fabricated citations."},
        },
    )

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
    )

    assert result.final_state == "MarkQuarantined"
    assert result.execution_status == "SUCCEEDED"


def test_run_adversarial_case_timeout():
    """Mock SFN always returns RUNNING; timeout fires quickly."""
    case = _make_case()
    sfn = MagicMock()
    sfn.start_execution.return_value = {
        "executionArn": "arn:aws:states:ap-southeast-2:123456789012:execution:test-sm:run-002"
    }
    sfn.describe_execution.return_value = {"status": "RUNNING", "output": None}

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
        poll_interval_sec=0.01,
        timeout_sec=0.05,
    )

    assert result.execution_status == "TIMED_OUT"
    assert result.error == "polling deadline"


def test_run_adversarial_case_output_missing_keys():
    """Missing output keys should default gracefully (0 findings, None judge_passed)."""
    case = _make_case(expected_outcome="judge_pass")
    sfn = _make_sfn_client(status="SUCCEEDED", output={})

    result = run_adversarial_case(
        case,
        sfn_arn="arn:aws:states:ap-southeast-2:123456789012:stateMachine:test-sm",
        s3_input_uri="s3://test-bucket/input.csv",
        sfn_client=sfn,
    )

    assert result.findings_count == 0
    assert result.judge_passed is None
    assert result.narrative_text is None
    assert result.final_state is None


# ---------------------------------------------------------------------------
# assert_outcome — pure logic, no AWS calls
# ---------------------------------------------------------------------------


def _make_result(**kwargs) -> AdversarialResult:
    defaults = dict(
        execution_status="SUCCEEDED",
        final_state="PublishTriage",
        findings_count=1,
        judge_passed=True,
        narrative_text="Some narrative.",
        error=None,
    )
    defaults.update(kwargs)
    return AdversarialResult(**defaults)


def test_assert_outcome_judge_pass_ok():
    case = _make_case(expected_outcome="judge_pass")
    result = _make_result(judge_passed=True)
    passed, failures = assert_outcome(case, result)
    assert passed is True
    assert failures == []


def test_assert_outcome_judge_pass_fail():
    case = _make_case(expected_outcome="judge_pass")
    result = _make_result(judge_passed=False)
    passed, failures = assert_outcome(case, result)
    assert passed is False
    assert len(failures) == 1
    assert "judge_passed" in failures[0]


def test_assert_outcome_judge_pass_none():
    """judge_passed=None should also fail the assertion (not truthy)."""
    case = _make_case(expected_outcome="judge_pass")
    result = _make_result(judge_passed=None)
    passed, failures = assert_outcome(case, result)
    assert passed is False


def test_assert_outcome_citation_gate_fail_ok():
    """Correct citation_gate_fail: SUCCEEDED + MarkQuarantined."""
    case = _make_case(expected_outcome="citation_gate_fail")
    result = _make_result(execution_status="SUCCEEDED", final_state="MarkQuarantined")
    passed, failures = assert_outcome(case, result)
    assert passed is True
    assert failures == []


def test_assert_outcome_citation_gate_fail_mismatch():
    """Citation gate expected but execution went to Publish instead."""
    case = _make_case(expected_outcome="citation_gate_fail")
    result = _make_result(execution_status="SUCCEEDED", final_state="Publish")
    passed, failures = assert_outcome(case, result)
    assert passed is False
    assert len(failures) == 1
    assert "MarkQuarantined" in failures[0]


def test_assert_outcome_narrative_no_findings_ok():
    case = _make_case(expected_outcome="narrative_no_findings")
    result = _make_result(findings_count=0)
    passed, failures = assert_outcome(case, result)
    assert passed is True


def test_assert_outcome_narrative_no_findings_fail():
    case = _make_case(expected_outcome="narrative_no_findings")
    result = _make_result(findings_count=5)
    passed, failures = assert_outcome(case, result)
    assert passed is False
    assert "findings_count=5" in failures[0]


def test_assert_outcome_rules_engine_error_ok():
    case = _make_case(expected_outcome="rules_engine_error")
    result = _make_result(execution_status="FAILED")
    passed, failures = assert_outcome(case, result)
    assert passed is True


def test_assert_outcome_rules_engine_error_mismatch():
    case = _make_case(expected_outcome="rules_engine_error")
    result = _make_result(execution_status="SUCCEEDED")
    passed, failures = assert_outcome(case, result)
    assert passed is False
    assert "FAILED" in failures[0]


def test_assert_outcome_agent_quotes_verbatim_ok():
    """agent_quotes_verbatim passes when judge_passed=True."""
    case = _make_case(expected_outcome="agent_quotes_verbatim")
    result = _make_result(judge_passed=True)
    passed, failures = assert_outcome(case, result)
    assert passed is True


def test_assert_outcome_agent_quotes_verbatim_fail():
    """agent_quotes_verbatim fails when judge_passed=False."""
    case = _make_case(expected_outcome="agent_quotes_verbatim")
    result = _make_result(judge_passed=False)
    passed, failures = assert_outcome(case, result)
    assert passed is False
    assert len(failures) == 1
