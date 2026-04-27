"""Tests for eval_harness.runner — orchestrates a full eval run."""
from __future__ import annotations

from unittest.mock import patch, call

import pytest

from src.eval_harness.runner import EvalCaseResult, _aggregate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(case_id: str, rule_ids=("R1", "R2", "R3", "R4", "R5", "R6")) -> EvalCaseResult:
    per_rule = {rid: {"precision": 1.0, "recall": 1.0} for rid in rule_ids}
    return EvalCaseResult(
        case_id=case_id,
        metrics={
            "faithfulness": 0.95,
            "answer_relevance": 0.90,
            "context_precision": 0.85,
            "bertscore_f1": 0.80,
            "per_rule": per_rule,
        },
        latency_ms=100,
        cost_aud=0.001,
    )


# ---------------------------------------------------------------------------
# Test _aggregate (pure-Python, no mocks needed)
# ---------------------------------------------------------------------------


def test_aggregate_computes_averages():
    """_aggregate averages each metric across EvalCaseResult instances."""
    results = [
        EvalCaseResult(
            case_id="case_a",
            metrics={
                "faithfulness": 1.0,
                "answer_relevance": 0.8,
                "context_precision": 0.6,
                "bertscore_f1": 0.7,
                "per_rule": {
                    "R1": {"precision": 1.0, "recall": 0.5},
                    "R2": {"precision": 0.0, "recall": 0.0},
                },
            },
            latency_ms=200,
            cost_aud=0.002,
        ),
        EvalCaseResult(
            case_id="case_b",
            metrics={
                "faithfulness": 0.0,
                "answer_relevance": 0.4,
                "context_precision": 0.2,
                "bertscore_f1": 0.3,
                "per_rule": {
                    "R1": {"precision": 0.0, "recall": 1.0},
                    "R2": {"precision": 1.0, "recall": 1.0},
                },
            },
            latency_ms=300,
            cost_aud=0.003,
        ),
    ]
    totals = _aggregate(results)

    assert totals["faithfulness_avg"] == pytest.approx(0.5)
    assert totals["answer_relevance_avg"] == pytest.approx(0.6)
    assert totals["context_precision_avg"] == pytest.approx(0.4)
    assert totals["bertscore_f1_avg"] == pytest.approx(0.5)
    assert totals["R1_precision_avg"] == pytest.approx(0.5)
    assert totals["R1_recall_avg"] == pytest.approx(0.75)
    assert totals["R2_precision_avg"] == pytest.approx(0.5)
    assert totals["R2_recall_avg"] == pytest.approx(0.5)
    assert totals["total_cases"] == 2
    assert totals["total_latency_ms"] == 500
    assert totals["total_cost_aud"] == pytest.approx(0.005)


def test_aggregate_empty_returns_empty_dict():
    """_aggregate with no results returns {}."""
    assert _aggregate([]) == {}


def test_aggregate_single_result():
    """_aggregate with a single result returns exact metric values."""
    results = [_make_result("solo")]
    totals = _aggregate(results)
    assert totals["faithfulness_avg"] == pytest.approx(0.95)
    assert totals["total_cases"] == 1
    assert totals["total_latency_ms"] == 100


# ---------------------------------------------------------------------------
# Smoke suite — 6 cases (one per rule R1–R6)
# ---------------------------------------------------------------------------


def test_run_eval_suite_smoke_runs_six_cases(monkeypatch):
    """run_eval_suite('smoke') runs exactly 6 cases (one per rule) in stub mode."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    with patch("src.eval_harness.runner.write_eval_result") as mock_writer:
        from src.eval_harness.runner import run_eval_suite

        result = run_eval_suite("smoke", branch="test-branch", commit_sha="abc123")

    assert result["suite"] == "smoke"
    assert result["cases_run"] == 6
    assert result["eval_run_id"].startswith("eval_")
    assert isinstance(result["totals"], dict)
    assert result["totals"]  # non-empty
    # Writer called once per case
    assert mock_writer.call_count == 6


def test_run_eval_suite_smoke_result_structure(monkeypatch):
    """Smoke suite result contains expected top-level keys."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    with patch("src.eval_harness.runner.write_eval_result"):
        from src.eval_harness.runner import run_eval_suite

        result = run_eval_suite("smoke", branch="main", commit_sha="deadbeef")

    assert set(result.keys()) >= {"eval_run_id", "suite", "cases_run", "results", "totals"}
    for r in result["results"]:
        assert "case_id" in r
        assert "metrics" in r
        assert "latency_ms" in r
        assert "cost_aud" in r


# ---------------------------------------------------------------------------
# Full suite — 10 golden + 6 adversarial = 16
# ---------------------------------------------------------------------------


def test_run_eval_suite_full_includes_adversarial(monkeypatch):
    """run_eval_suite('full') runs all 10 golden + 6 adversarial = 16 cases in stub mode."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    with patch("src.eval_harness.runner.write_eval_result") as mock_writer:
        from src.eval_harness.runner import run_eval_suite

        result = run_eval_suite("full", branch="feat/test", commit_sha="cafebabe")

    assert result["cases_run"] == 16
    assert mock_writer.call_count == 16


# ---------------------------------------------------------------------------
# DDB write called once per case
# ---------------------------------------------------------------------------


def test_run_eval_suite_writes_to_ddb_per_case(monkeypatch):
    """write_eval_result is called once per case with the eval_run_id and case_id."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    with patch("src.eval_harness.runner.write_eval_result") as mock_writer:
        from src.eval_harness.runner import run_eval_suite

        result = run_eval_suite("smoke", branch="feat/eval", commit_sha="11223344")

    eval_run_id = result["eval_run_id"]
    # Each call must include the eval_run_id
    for c in mock_writer.call_args_list:
        assert c.args[0] == eval_run_id
    # All 6 case_ids must appear in write calls
    written_case_ids = {c.args[1] for c in mock_writer.call_args_list}
    assert len(written_case_ids) == 6


# ---------------------------------------------------------------------------
# Adversarial cases (no expected_findings) handled gracefully in stub mode
# ---------------------------------------------------------------------------


def test_run_one_stub_handles_adversarial_case(monkeypatch):
    """_run_one_stub handles AdversarialCase (no expected_findings) without raising."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    from src.shared.models import AdversarialCase
    from src.eval_harness.runner import _run_one_stub

    adv = AdversarialCase(
        case_id="adv_test_001",
        description="Prompt injection attempt",
        input_csv=None,
        generator_fn=None,
        expected_outcome="judge_pass",
        expected_assertions=["judge passed"],
    )

    result = _run_one_stub(adv, "eval_run_test")

    assert result.case_id == "adv_test_001"
    assert result.latency_ms == 100
    assert result.cost_aud == 0.001
    assert "faithfulness" in result.metrics
    assert "per_rule" in result.metrics


# ---------------------------------------------------------------------------
# Stub metric values are as specified
# ---------------------------------------------------------------------------


def test_run_one_stub_returns_specified_metrics(monkeypatch):
    """_run_one_stub returns the exact stub metric values from the design doc."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    from src.eval_harness.golden_loader import load_case_by_id
    from src.eval_harness.runner import _run_one_stub

    case = load_case_by_id("case_001_baseline")
    result = _run_one_stub(case, "eval_run_123")

    assert result.metrics["faithfulness"] == pytest.approx(0.95)
    assert result.metrics["answer_relevance"] == pytest.approx(0.90)
    assert result.metrics["context_precision"] == pytest.approx(0.85)
    assert result.metrics["bertscore_f1"] == pytest.approx(0.80)
    assert result.latency_ms == 100
    assert result.cost_aud == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# Real mode raises NotImplementedError
# ---------------------------------------------------------------------------


def test_run_one_real_raises_not_implemented(monkeypatch):
    """_run_one_real raises NotImplementedError (real Lambda path not wired in unit tests)."""
    from src.eval_harness.runner import _run_one_real
    from src.eval_harness.golden_loader import load_case_by_id

    case = load_case_by_id("case_001_baseline")
    with pytest.raises(NotImplementedError):
        _run_one_real(case, "eval_run_456")


# ---------------------------------------------------------------------------
# Totals contain cross-rule averages
# ---------------------------------------------------------------------------


def test_run_eval_suite_smoke_totals_has_precision_avg(monkeypatch):
    """Smoke suite totals dict includes precision_avg and recall_avg for reporter threshold table."""
    monkeypatch.setenv("STUB_BEDROCK", "1")

    with patch("src.eval_harness.runner.write_eval_result"):
        from src.eval_harness.runner import run_eval_suite

        result = run_eval_suite("smoke", branch="main", commit_sha="xyz")

    totals = result["totals"]
    assert "precision_avg" in totals
    assert "recall_avg" in totals
    assert "total_cases" in totals
    assert "total_latency_ms" in totals
    assert "total_cost_aud" in totals
