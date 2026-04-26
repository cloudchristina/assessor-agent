"""Property-based invariants for the rules engine.

Two tiers:
  - Default (max_examples=200): runs in <30s for fast TDD feedback.
    Invoked by the normal `pytest tests/unit/` suite.
  - Slow (max_examples=10_000): gated behind `pytest --run-slow`.
    Invoked by the `eval-property` make target in CI.
    Run manually: pytest tests/unit/test_property_invariants.py -k slow --run-slow

The `summary` dict returned by `run_rules` contains BOTH rule-ID keys ("R1"…"R6")
AND severity keys ("CRITICAL", "HIGH", etc.).  Invariant 1 therefore sums only the
rule-ID keys so the count matches `len(out.findings)` exactly.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from evals.property.invariants import _RULE_IDS, uar_row_strategy
from src.rules_engine.engine import run_rules
from src.rules_engine.rules import RULES


# ---------------------------------------------------------------------------
# Shared invariant checker
# ---------------------------------------------------------------------------


def _check_invariants(rows: list) -> None:
    out = run_rules(rows, run_id="prop_test", rules=RULES)

    # Invariant 1: len(findings) == sum of per-rule counts in summary
    rule_only_sum = sum(v for k, v in out.summary.items() if k in _RULE_IDS)
    assert len(out.findings) == rule_only_sum, (
        f"finding count {len(out.findings)} != rule-key sum {rule_only_sum}; "
        f"summary={out.summary}"
    )

    # Invariant 2: every finding's principal appears in the input rows
    principals = {r.login_name for r in rows}
    bad_principals = [f.principal for f in out.findings if f.principal not in principals]
    assert not bad_principals, (
        f"Findings reference principals absent from input rows: {bad_principals}"
    )

    # Invariant 3: every finding has a known rule_id
    bad_rule_ids = [f.rule_id for f in out.findings if f.rule_id not in _RULE_IDS]
    assert not bad_rule_ids, f"Unknown rule IDs in findings: {bad_rule_ids}"

    # Invariant 4: finding_ids are unique within the run
    all_ids = [f.finding_id for f in out.findings]
    assert len(set(all_ids)) == len(all_ids), (
        "Duplicate finding_ids detected: "
        + str([fid for fid in all_ids if all_ids.count(fid) > 1])
    )


# ---------------------------------------------------------------------------
# Default variant — fast (200 examples, max 200 rows per example)
# ---------------------------------------------------------------------------


@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(rows=st.lists(uar_row_strategy(), min_size=0, max_size=200))
def test_rules_engine_invariants(rows: list) -> None:
    """Fast property test — runs in <30s, part of the normal unit suite."""
    _check_invariants(rows)


# ---------------------------------------------------------------------------
# Slow variant — 10k examples, gated by --run-slow
# ---------------------------------------------------------------------------


@pytest.mark.slow
@settings(
    max_examples=10_000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(rows=st.lists(uar_row_strategy(), min_size=0, max_size=5000))
def test_rules_engine_invariants_full(rows: list) -> None:
    """Slow variant — gated by `pytest --run-slow` mark filter, see conftest.

    CI runs this via the `eval-property` make target:
        pytest tests/unit/test_property_invariants.py --run-slow
    """
    _check_invariants(rows)
