"""Kolmogorov-Smirnov 2-sample drift test (pure Python, no scipy dependency).

scipy was originally used here, but it bloats the Lambda package past the 250MB
unzipped limit when shared via lambda-requirements.txt. This implementation uses
the standard 2-sample KS statistic (max |F1(x) - F2(x)| over the merged support)
and the asymptotic Smirnov p-value approximation, which is sufficient for the
drift-detection threshold-comparison use case.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


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
    statistic, pvalue = _ks_2samp(recent, baseline)
    return KSResult(
        statistic=statistic,
        pvalue=pvalue,
        drift_detected=pvalue < alpha,
        n_recent=len(recent),
        n_baseline=len(baseline),
    )


def _ks_2samp(a: list[float], b: list[float]) -> tuple[float, float]:
    """Two-sample KS statistic + asymptotic Smirnov p-value.

    Statistic = max over the merged support of |F_a(x) - F_b(x)| where F is the
    empirical CDF. p-value uses the Kolmogorov asymptotic series:
        Q(λ) = 2 * Σ_{k=1..∞} (-1)^(k-1) * exp(-2 k² λ²)
    with λ = (sqrt(n_eff) + 0.12 + 0.11/sqrt(n_eff)) * D, n_eff = n_a*n_b/(n_a+n_b).
    """
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    na, nb = len(a_sorted), len(b_sorted)
    # Walk by distinct x-values: advance both empirical CDFs past x before
    # measuring the difference. This is the standard tie-handling for 2-sample KS.
    i = j = 0
    d_max = 0.0
    while i < na or j < nb:
        if i < na and j < nb:
            x = min(a_sorted[i], b_sorted[j])
        elif i < na:
            x = a_sorted[i]
        else:
            x = b_sorted[j]
        while i < na and a_sorted[i] <= x:
            i += 1
        while j < nb and b_sorted[j] <= x:
            j += 1
        diff = abs(i / na - j / nb)
        if diff > d_max:
            d_max = diff
    d_max = float(d_max)

    if d_max == 0.0:
        return 0.0, 1.0  # identical empirical distributions

    n_eff = na * nb / (na + nb)
    sqrt_neff = math.sqrt(n_eff)
    lam = (sqrt_neff + 0.12 + 0.11 / sqrt_neff) * d_max

    # Kolmogorov asymptotic distribution; converges very fast for lam > 0.
    pvalue = 0.0
    for k in range(1, 101):
        term = 2 * (-1) ** (k - 1) * math.exp(-2 * (k * lam) ** 2)
        pvalue += term
        if abs(term) < 1e-12:
            break
    pvalue = min(1.0, max(0.0, pvalue))
    return float(d_max), float(pvalue)
