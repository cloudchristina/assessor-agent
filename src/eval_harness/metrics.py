"""Per-rule precision/recall, computed by matching (rule_id, principal) tuples."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class RuleMetric:
    rule_id: str
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 1.0  # no predictions, no FPs
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 1.0  # no expected, vacuously perfect
        return self.true_positives / (self.true_positives + self.false_negatives)


def per_rule_precision_recall(
    actual: list[dict],
    expected: list[dict],
    rule_ids: list[str],
) -> dict[str, RuleMetric]:
    """Match by (rule_id, principal). Both inputs are lists of dicts with at
    minimum {rule_id, principal} keys."""
    out: dict[str, RuleMetric] = {}
    for rid in rule_ids:
        a = {(f["rule_id"], f["principal"]) for f in actual if f["rule_id"] == rid}
        e = {(f["rule_id"], f["principal"]) for f in expected if f["rule_id"] == rid}
        tp = len(a & e)
        fp = len(a - e)
        fn = len(e - a)
        out[rid] = RuleMetric(rule_id=rid, true_positives=tp, false_positives=fp, false_negatives=fn)
    return out
