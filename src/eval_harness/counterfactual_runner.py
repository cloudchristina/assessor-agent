"""Run counterfactual generators against the rules engine and assert proper isolation.

A counterfactual is (base_rows, mutated_rows, rule_id_targeted) where:
- base_rows:    fires the targeted rule at least once.
- mutated_rows: same rows with ONE attribute flipped to suppress exactly that rule.

Assertions checked:
1. targeted_rule_changed  — base fires more of rule_id than mutated does.
2. other_rules_unchanged  — every other rule's count is identical across both runs.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.rules_engine.engine import run_rules
from src.rules_engine.rules import RULES
from src.shared.models import UARRow


@dataclass(frozen=True)
class CounterfactualResult:
    rule_id: str
    base_summary: dict[str, int]
    mutated_summary: dict[str, int]
    targeted_rule_changed: bool
    other_rules_unchanged: bool


def run_counterfactual(
    generator: Callable[[], tuple[list[dict], list[dict], str]],
) -> CounterfactualResult:
    """Run one generator and return a result with isolation assertions."""
    base_rows_raw, mutated_rows_raw, rule_id = generator()

    base_typed = [UARRow.model_validate(r) for r in base_rows_raw]
    mutated_typed = [UARRow.model_validate(r) for r in mutated_rows_raw]

    base_out = run_rules(base_typed, run_id="cf_base", rules=RULES)
    mutated_out = run_rules(mutated_typed, run_id="cf_mutated", rules=RULES)

    # Build per-rule counts from the summary (engine always includes all rule IDs).
    base_summary = {r.rule_id: base_out.summary.get(r.rule_id, 0) for r in RULES}
    mut_summary = {r.rule_id: mutated_out.summary.get(r.rule_id, 0) for r in RULES}

    targeted_changed = base_summary[rule_id] > mut_summary[rule_id]
    other_unchanged = all(
        base_summary[rid] == mut_summary[rid]
        for rid in base_summary
        if rid != rule_id
    )

    return CounterfactualResult(
        rule_id=rule_id,
        base_summary=base_summary,
        mutated_summary=mut_summary,
        targeted_rule_changed=targeted_changed,
        other_rules_unchanged=other_unchanged,
    )


def run_all_counterfactuals() -> list[CounterfactualResult]:
    """Run every generator in the registry and return all results."""
    from evals.counterfactual.generators import GENERATORS

    return [run_counterfactual(g) for g in GENERATORS]
