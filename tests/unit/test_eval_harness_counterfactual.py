"""Tests for the counterfactual runner (Task 3.4).

Each per-rule counterfactual flips exactly one input attribute and asserts:
1. The targeted rule fires fewer times on mutated_rows than on base_rows.
2. All other rules fire the same number of times on both inputs.
"""
from __future__ import annotations

import pytest

from evals.counterfactual.generators import GENERATORS
from src.eval_harness.counterfactual_runner import (
    CounterfactualResult,
    run_all_counterfactuals,
    run_counterfactual,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_for(rule_id: str):
    """Return the generator whose third tuple element equals rule_id."""
    for g in GENERATORS:
        result = g()
        if result[2] == rule_id:
            return g
    raise ValueError(f"No generator found for {rule_id}")


# ---------------------------------------------------------------------------
# Omnibus test: all 6 counterfactuals must isolate cleanly in one shot
# ---------------------------------------------------------------------------

def test_all_counterfactuals_isolate_their_rule():
    """Each per-rule counterfactual should flip exactly one rule's findings.

    Assertions:
    - 6 results (one per rule R1-R6).
    - targeted_rule_changed is True for every result.
    - other_rules_unchanged is True for every result.
    """
    results = run_all_counterfactuals()
    assert len(results) == 6, f"Expected 6 results, got {len(results)}"
    for r in results:
        assert isinstance(r, CounterfactualResult)
        assert r.targeted_rule_changed, (
            f"{r.rule_id}: targeted rule did NOT change - "
            f"base={r.base_summary}, mutated={r.mutated_summary}"
        )
        assert r.other_rules_unchanged, (
            f"{r.rule_id}: other rules changed - "
            f"base={r.base_summary}, mutated={r.mutated_summary}"
        )


# ---------------------------------------------------------------------------
# Per-rule parametrised tests - faster to debug individual failures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule_id", ["R1", "R2", "R3", "R4", "R5", "R6"])
def test_per_rule_counterfactual_individually(rule_id: str):
    """Per-rule sanity check - easier debugging if a single rule's counterfactual fails."""
    gen = _gen_for(rule_id)
    result = run_counterfactual(gen)

    assert result.rule_id == rule_id
    assert result.targeted_rule_changed, (
        f"{rule_id}: base={result.base_summary}, mutated={result.mutated_summary}"
    )
    assert result.other_rules_unchanged, (
        f"{rule_id}: base={result.base_summary}, mutated={result.mutated_summary}"
    )


# ---------------------------------------------------------------------------
# Structural tests - verify the result dataclass fields
# ---------------------------------------------------------------------------

def test_counterfactual_result_fields():
    """CounterfactualResult exposes the right fields."""
    gen = _gen_for("R1")
    result = run_counterfactual(gen)

    assert isinstance(result.rule_id, str)
    assert isinstance(result.base_summary, dict)
    assert isinstance(result.mutated_summary, dict)
    assert isinstance(result.targeted_rule_changed, bool)
    assert isinstance(result.other_rules_unchanged, bool)
    # Both summaries must contain all six rule keys.
    for rid in ("R1", "R2", "R3", "R4", "R5", "R6"):
        assert rid in result.base_summary, f"{rid} missing from base_summary"
        assert rid in result.mutated_summary, f"{rid} missing from mutated_summary"


def test_base_rows_fire_targeted_rule():
    """The base rows for each generator must produce at least one finding of the targeted rule."""
    from src.rules_engine.engine import run_rules
    from src.rules_engine.rules import RULES
    from src.shared.models import UARRow

    for gen in GENERATORS:
        base_rows_raw, _mutated, rule_id = gen()
        base_typed = [UARRow.model_validate(r) for r in base_rows_raw]
        out = run_rules(base_typed, run_id="cf_base_check", rules=RULES)
        count = out.summary.get(rule_id, 0)
        assert count > 0, (
            f"Generator for {rule_id}: base rows produced 0 findings "
            f"(summary={out.summary})"
        )


def test_mutated_rows_suppress_targeted_rule():
    """The mutated rows for each generator must produce ZERO findings of the targeted rule."""
    from src.rules_engine.engine import run_rules
    from src.rules_engine.rules import RULES
    from src.shared.models import UARRow

    for gen in GENERATORS:
        _base, mutated_rows_raw, rule_id = gen()
        mutated_typed = [UARRow.model_validate(r) for r in mutated_rows_raw]
        out = run_rules(mutated_typed, run_id="cf_mutated_check", rules=RULES)
        count = out.summary.get(rule_id, 0)
        assert count == 0, (
            f"Generator for {rule_id}: mutated rows still produced {count} findings "
            f"(summary={out.summary})"
        )
