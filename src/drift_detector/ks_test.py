"""Kolmogorov-Smirnov 2-sample drift test wrapper around scipy.stats.ks_2samp."""
from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import ks_2samp


@dataclass(frozen=True)
class KSResult:
    statistic: float  # KS statistic in [0, 1]
    pvalue: float  # p-value in [0, 1]
    drift_detected: bool
    n_recent: int
    n_baseline: int


def ks_drift(
    recent: list[float],
    baseline: list[float],
    *,
    alpha: float = 0.05,
    min_samples: int = 5,
) -> KSResult:
    """Two-sample KS test. drift_detected = pvalue < alpha (rejecting null of equal distributions).

    Returns drift_detected=False with statistic=0.0 if either sample size < min_samples.
    """
    if len(recent) < min_samples or len(baseline) < min_samples:
        return KSResult(
            statistic=0.0,
            pvalue=1.0,
            drift_detected=False,
            n_recent=len(recent),
            n_baseline=len(baseline),
        )
    res = ks_2samp(recent, baseline)
    return KSResult(
        statistic=float(res.statistic),
        pvalue=float(res.pvalue),
        drift_detected=bool(res.pvalue < alpha),
        n_recent=len(recent),
        n_baseline=len(baseline),
    )
