"""Tests for bertscore_runner wrapper.

BERTScore requires downloading multi-GB models, so we mock the score function
entirely via unittest.mock.patch to avoid any actual downloads or computation.
"""
from __future__ import annotations

from unittest.mock import patch

from src.eval_harness.bertscore_runner import bertscore_vs_reference

# ---------------------------------------------------------------------------
# Test 1 — bertscore_vs_reference returns float in [0, 1]
# ---------------------------------------------------------------------------


def test_bertscore_returns_float_in_unit_range():
    """Mock score to return known F1=[0.82]; assert returned value == 0.82."""
    with patch("src.eval_harness.bertscore_runner.score") as mock_score:
        # score returns (P, R, F1) where each is a list-like (or tensor)
        mock_score.return_value = ([0.8], [0.85], [0.82])

        result = bertscore_vs_reference(
            narrative_text="The principal sa has sysadmin.",
            reference_text="Principal sa is admin.",
        )

    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0
    assert result == 0.82


# ---------------------------------------------------------------------------
# Test 2 — bertscore_vs_reference clamps above 1.0
# ---------------------------------------------------------------------------


def test_bertscore_clamps_above_one():
    """Mock score to return F1=[1.05]; assert returned value == 1.0."""
    with patch("src.eval_harness.bertscore_runner.score") as mock_score:
        mock_score.return_value = ([1.0], [1.0], [1.05])

        result = bertscore_vs_reference(
            narrative_text="Text A",
            reference_text="Text B",
        )

    assert result == 1.0


# ---------------------------------------------------------------------------
# Test 3 — bertscore_vs_reference clamps below 0.0
# ---------------------------------------------------------------------------


def test_bertscore_clamps_below_zero():
    """Mock score to return F1=[-0.1]; assert returned value == 0.0."""
    with patch("src.eval_harness.bertscore_runner.score") as mock_score:
        mock_score.return_value = ([0.0], [0.0], [-0.1])

        result = bertscore_vs_reference(
            narrative_text="Text A",
            reference_text="Text B",
        )

    assert result == 0.0


# ---------------------------------------------------------------------------
# Test 4 — bertscore_vs_reference passes model_type to score
# ---------------------------------------------------------------------------


def test_bertscore_passes_model_type():
    """Call with custom model_type; assert score was called with it."""
    with patch("src.eval_harness.bertscore_runner.score") as mock_score:
        mock_score.return_value = ([0.9], [0.9], [0.9])

        bertscore_vs_reference(
            narrative_text="Text A",
            reference_text="Text B",
            model_type="custom-model-xyz",
        )

    # Verify score was called with the correct model_type kwarg
    assert mock_score.called
    call_kwargs = mock_score.call_args.kwargs
    assert call_kwargs["model_type"] == "custom-model-xyz"
