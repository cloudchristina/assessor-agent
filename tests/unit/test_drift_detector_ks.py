"""Tests for drift_detector.ks_test — pure KS stat module, no AWS mocks needed."""
from __future__ import annotations

import pytest

from src.drift_detector.ks_test import KSResult, ks_drift


# ---------------------------------------------------------------------------
# test_identical_distributions_no_drift
# ---------------------------------------------------------------------------


def test_identical_distributions_no_drift() -> None:
    """Two identical distributions: pvalue==1.0, drift_detected==False."""
    recent = [0.9] * 20
    baseline = [0.9] * 20
    result = ks_drift(recent, baseline)

    assert isinstance(result, KSResult)
    assert result.drift_detected is False  # plain bool from implementation
    assert result.pvalue == pytest.approx(1.0)
    assert result.statistic == pytest.approx(0.0)
    assert result.n_recent == 20
    assert result.n_baseline == 20


# ---------------------------------------------------------------------------
# test_clearly_different_distributions_detect_drift
# ---------------------------------------------------------------------------


def test_clearly_different_distributions_detect_drift() -> None:
    """Clearly separated distributions: drift_detected==True, pvalue < 0.05."""
    recent = [0.9] * 20
    baseline = [0.5] * 20
    result = ks_drift(recent, baseline)

    assert result.drift_detected is True
    assert result.pvalue < 0.05
    assert result.statistic > 0.0
    assert result.n_recent == 20
    assert result.n_baseline == 20


# ---------------------------------------------------------------------------
# test_insufficient_samples_returns_no_drift
# ---------------------------------------------------------------------------


def test_insufficient_samples_returns_no_drift() -> None:
    """Either sample below min_samples=5: always drift_detected=False, pvalue=1.0."""
    # recent too small
    result = ks_drift([0.9, 0.8, 0.7], [0.5] * 20)
    assert result.drift_detected is False
    assert result.pvalue == pytest.approx(1.0)
    assert result.statistic == pytest.approx(0.0)
    assert result.n_recent == 3
    assert result.n_baseline == 20

    # baseline too small
    result2 = ks_drift([0.9] * 20, [0.5, 0.4])
    assert result2.drift_detected is False
    assert result2.pvalue == pytest.approx(1.0)
    assert result2.n_recent == 20
    assert result2.n_baseline == 2

    # both too small
    result3 = ks_drift([], [])
    assert result3.drift_detected is False
    assert result3.n_recent == 0
    assert result3.n_baseline == 0


# ---------------------------------------------------------------------------
# test_alpha_threshold_governs_decision
# ---------------------------------------------------------------------------


def test_alpha_threshold_governs_decision() -> None:
    """Same data, alpha=0.001 vs alpha=0.5 should yield different drift decisions
    for a moderately different distribution."""
    # Use a borderline distribution — some separation but not extreme
    import random

    rng = random.Random(42)
    recent = [rng.gauss(0.85, 0.05) for _ in range(30)]
    baseline = [rng.gauss(0.75, 0.05) for _ in range(30)]

    # With a strict alpha (0.001) we may not detect drift
    result_strict = ks_drift(recent, baseline, alpha=0.001)
    # With a lax alpha (0.5) we are more likely to detect drift
    result_lax = ks_drift(recent, baseline, alpha=0.5)

    # Both use same statistic/pvalue; only drift_detected differs based on alpha
    assert result_strict.statistic == pytest.approx(result_lax.statistic)
    assert result_strict.pvalue == pytest.approx(result_lax.pvalue)

    # With lax alpha=0.5, pvalue almost certainly < 0.5 for these distributions
    assert result_lax.drift_detected is True

    # With strict alpha=0.001, only detect if pvalue < 0.001
    assert result_strict.drift_detected == (result_strict.pvalue < 0.001)
