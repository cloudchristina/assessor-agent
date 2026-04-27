"""Tests for per-rule precision/recall metrics."""
from src.eval_harness.metrics import per_rule_precision_recall, RuleMetric


def test_perfect_match_yields_1_0():
    expected = [{"rule_id": "R1", "principal": "alice"}]
    actual = [{"rule_id": "R1", "principal": "alice"}]
    metrics = per_rule_precision_recall(actual, expected, rule_ids=["R1"])
    assert metrics["R1"].precision == 1.0
    assert metrics["R1"].recall == 1.0


def test_false_positive_drops_precision():
    expected = [{"rule_id": "R1", "principal": "alice"}]
    actual = [
        {"rule_id": "R1", "principal": "alice"},
        {"rule_id": "R1", "principal": "bob"},  # FP
    ]
    metrics = per_rule_precision_recall(actual, expected, rule_ids=["R1"])
    assert metrics["R1"].precision == 0.5
    assert metrics["R1"].recall == 1.0


def test_false_negative_drops_recall():
    expected = [
        {"rule_id": "R1", "principal": "alice"},
        {"rule_id": "R1", "principal": "bob"},
    ]
    actual = [{"rule_id": "R1", "principal": "alice"}]
    metrics = per_rule_precision_recall(actual, expected, rule_ids=["R1"])
    assert metrics["R1"].precision == 1.0
    assert metrics["R1"].recall == 0.5


def test_zero_expected_zero_actual_is_nan_safe():
    metrics = per_rule_precision_recall([], [], rule_ids=["R1"])
    # By convention: precision=1.0, recall=1.0 when both are empty
    assert metrics["R1"].precision == 1.0
    assert metrics["R1"].recall == 1.0
