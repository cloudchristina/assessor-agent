"""Tests for ragas_runner wrapper.

Ragas calls an LLM by default; we stub it out entirely using sys.modules
patching so the unit tests never touch a real model or the network.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Pre-patch ragas + datasets before any project import can trigger a real
# ragas import (ragas requires 'rich' which may not be in the venv).
# ---------------------------------------------------------------------------

_ragas_stub = MagicMock()
_ragas_metrics_stub = MagicMock()
for _mod in ("ragas", "ragas.evaluation", "ragas.metrics"):
    sys.modules.setdefault(_mod, MagicMock())

# Now it's safe to import our module
from src.eval_harness.ragas_runner import (  # noqa: E402
    _finding_to_context,
    compute_ragas_metrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FINDING = {
    "finding_id": "f-001",
    "rule_id": "R1",
    "severity": "CRITICAL",
    "principal": "sa",
    "databases": ["MortgageDB"],
    "ism_controls": ["ISM-1546"],
    "evidence": {"login_type": "SQL_LOGIN"},
}

SAMPLE_FINDINGS = [SAMPLE_FINDING]
SAMPLE_NARRATIVE = (
    "The access review identified a SQL authentication login 'sa' with sysadmin "
    "privileges on MortgageDB, violating ISM-1546."
)
SAMPLE_MUST_MENTION = ["sa", "ISM-1546", "MortgageDB"]


# ---------------------------------------------------------------------------
# Test 1 — compute_ragas_metrics returns three floats in [0, 1]
# ---------------------------------------------------------------------------


def test_compute_ragas_metrics_returns_three_floats():
    """With a mocked evaluate, the wrapper returns three float-valued keys."""
    mock_result = {"faithfulness": 0.85, "answer_relevancy": 0.92, "context_precision": 0.78}

    with patch("src.eval_harness.ragas_runner.evaluate", return_value=mock_result):
        out = compute_ragas_metrics(
            narrative_text=SAMPLE_NARRATIVE,
            findings=SAMPLE_FINDINGS,
            must_mention=SAMPLE_MUST_MENTION,
        )

    assert set(out.keys()) == {"faithfulness", "answer_relevance", "context_precision"}
    for key, value in out.items():
        assert isinstance(value, float), f"{key} should be float, got {type(value)}"
        assert 0.0 <= value <= 1.0, f"{key}={value} not in [0, 1]"


# ---------------------------------------------------------------------------
# Test 2 — _finding_to_context format
# ---------------------------------------------------------------------------


def test_finding_to_context_format():
    """_finding_to_context encodes all seven fields in the output string."""
    ctx = _finding_to_context(SAMPLE_FINDING)

    assert "finding_id=f-001" in ctx
    assert "rule_id=R1" in ctx
    assert "severity=CRITICAL" in ctx
    assert "principal=sa" in ctx
    assert "databases=" in ctx
    assert "ism_controls=" in ctx
    assert "evidence=" in ctx
    # Fields are pipe-separated
    assert " | " in ctx


# ---------------------------------------------------------------------------
# Test 3 — compute_ragas_metrics passes correct Dataset to ragas.evaluate
# ---------------------------------------------------------------------------


def test_compute_passes_dataset_to_ragas():
    """evaluate is called once; the Dataset's answer[0] equals narrative_text."""
    from datasets import Dataset  # safe — datasets has no rich dependency

    mock_result = {"faithfulness": 1.0, "answer_relevancy": 1.0, "context_precision": 1.0}
    captured: list[Dataset] = []

    def _fake_evaluate(dataset, **kwargs):
        captured.append(dataset)
        return mock_result

    with patch("src.eval_harness.ragas_runner.evaluate", side_effect=_fake_evaluate):
        compute_ragas_metrics(
            narrative_text=SAMPLE_NARRATIVE,
            findings=SAMPLE_FINDINGS,
            must_mention=SAMPLE_MUST_MENTION,
        )

    assert len(captured) == 1, "evaluate should be called exactly once"
    ds = captured[0]
    assert ds["answer"][0] == SAMPLE_NARRATIVE
    assert ds["question"][0] == "Summarise the access-review findings for this cycle"
    assert ds["ground_truth"][0] == " ".join(SAMPLE_MUST_MENTION)
    # contexts is a list of context strings (one per finding)
    assert len(ds["contexts"][0]) == len(SAMPLE_FINDINGS)


# ---------------------------------------------------------------------------
# Test 4 — empty findings and must_mention still work
# ---------------------------------------------------------------------------


def test_compute_ragas_metrics_empty_inputs():
    """Works with no findings and a single must_mention item."""
    mock_result = {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5}

    with patch("src.eval_harness.ragas_runner.evaluate", return_value=mock_result):
        out = compute_ragas_metrics(
            narrative_text="No findings this cycle.",
            findings=[],
            must_mention=["placeholder"],
        )

    assert out["faithfulness"] == 0.5
    assert out["answer_relevance"] == 0.5
    assert out["context_precision"] == 0.5
