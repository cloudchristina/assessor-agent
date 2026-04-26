"""Tests for src/eval_harness/reporter.py (Task 4.2)."""
from __future__ import annotations

from src.eval_harness.reporter import _status_for, render_markdown_diff

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CURRENT_RUN = {
    "eval_run_id": "eval_20260425T1200_abc123",
    "suite": "smoke",
    "cases_run": 6,
    "results": [],
    "totals": {
        "faithfulness_avg": 0.92,
        "answer_relevance_avg": 0.86,
        "context_precision_avg": 0.84,
        "bertscore_f1_avg": 0.78,
        "precision_avg": 0.95,
        "recall_avg": 0.93,
    },
}

BASELINE_RUN = {
    "eval_run_id": "eval_20260418T1200_xyz789",
    "suite": "smoke",
    "cases_run": 6,
    "results": [],
    "totals": {
        "faithfulness_avg": 0.87,
        "answer_relevance_avg": 0.91,
        "context_precision_avg": 0.79,
        "bertscore_f1_avg": 0.73,
        "precision_avg": 0.90,
        "recall_avg": 0.88,
    },
}


# ---------------------------------------------------------------------------
# Table structure tests
# ---------------------------------------------------------------------------


def test_render_with_baseline_shows_5col_table():
    md = render_markdown_diff(CURRENT_RUN, BASELINE_RUN)
    assert "| Metric | Current | Baseline | Δ | Status |" in md
    # baseline eval_run_id appears
    assert "eval_20260418T1200_xyz789" in md
    # current eval_run_id appears
    assert "eval_20260425T1200_abc123" in md
    # all totals keys appear as rows
    for k in CURRENT_RUN["totals"]:
        assert f"`{k}`" in md


def test_render_no_baseline_shows_3col_table():
    md = render_markdown_diff(CURRENT_RUN, None)
    assert "| Metric | Current | Status |" in md
    # no 5-col header
    assert "| Metric | Current | Baseline | Δ | Status |" not in md
    # first-run message
    assert "first run" in md.lower() or "no baseline" in md.lower() or "none" in md.lower()
    # current id still present
    assert "eval_20260425T1200_abc123" in md


def test_render_no_baseline_shows_all_current_totals():
    md = render_markdown_diff(CURRENT_RUN, None)
    for k in CURRENT_RUN["totals"]:
        assert f"`{k}`" in md


# ---------------------------------------------------------------------------
# Status emoji / threshold tests
# ---------------------------------------------------------------------------


def test_status_emoji_faithfulness_fail():
    assert _status_for("faithfulness", 0.80) == "❌"


def test_status_emoji_faithfulness_warn():
    # 0.90 is >= 0.85 (fail) but < 0.92 (warn threshold)
    assert _status_for("faithfulness", 0.90) == "⚠️"


def test_status_emoji_faithfulness_ok():
    assert _status_for("faithfulness", 0.95) == "✅"


def test_status_emoji_answer_relevance_fail():
    assert _status_for("answer_relevance", 0.79) == "❌"


def test_status_emoji_answer_relevance_warn():
    assert _status_for("answer_relevance", 0.83) == "⚠️"


def test_status_emoji_answer_relevance_ok():
    assert _status_for("answer_relevance", 0.90) == "✅"


def test_status_emoji_bertscore_f1_fail():
    assert _status_for("bertscore_f1", 0.65) == "❌"


def test_status_emoji_bertscore_f1_warn():
    assert _status_for("bertscore_f1", 0.75) == "⚠️"


def test_status_emoji_bertscore_f1_ok():
    assert _status_for("bertscore_f1", 0.85) == "✅"


def test_status_emoji_precision_avg_fail():
    assert _status_for("precision_avg", 0.89) == "❌"


def test_status_emoji_precision_avg_warn():
    assert _status_for("precision_avg", 0.92) == "⚠️"


def test_status_emoji_precision_avg_ok():
    assert _status_for("precision_avg", 0.97) == "✅"


def test_status_emoji_recall_avg_fail():
    assert _status_for("recall_avg", 0.89) == "❌"


def test_status_emoji_recall_avg_ok():
    assert _status_for("recall_avg", 0.96) == "✅"


# ---------------------------------------------------------------------------
# Delta sign tests
# ---------------------------------------------------------------------------


def test_delta_positive():
    """When current > baseline, delta cell shows a leading '+'."""
    cur = {**CURRENT_RUN, "totals": {"faithfulness_avg": 0.95}}
    base = {**BASELINE_RUN, "totals": {"faithfulness_avg": 0.90}}
    md = render_markdown_diff(cur, base)
    assert "+0.0500" in md


def test_delta_negative():
    """When current < baseline, delta cell shows a leading '-'."""
    cur = {**CURRENT_RUN, "totals": {"faithfulness_avg": 0.85}}
    base = {**BASELINE_RUN, "totals": {"faithfulness_avg": 0.90}}
    md = render_markdown_diff(cur, base)
    assert "-0.0500" in md


def test_delta_zero():
    """Identical values produce +0.0000."""
    cur = {**CURRENT_RUN, "totals": {"faithfulness_avg": 0.90}}
    base = {**BASELINE_RUN, "totals": {"faithfulness_avg": 0.90}}
    md = render_markdown_diff(cur, base)
    assert "+0.0000" in md


# ---------------------------------------------------------------------------
# Metric not in threshold table
# ---------------------------------------------------------------------------


def test_metric_not_in_threshold_table_defaults_ok():
    """Metrics outside the threshold dict (e.g. latency_ms_avg) always show ✅."""
    cur = {**CURRENT_RUN, "totals": {"latency_ms_avg": 9999.0}}
    md = render_markdown_diff(cur, None)
    # The row for latency_ms_avg should show ✅
    lines = [line for line in md.splitlines() if "latency_ms_avg" in line]
    assert lines, "Expected a row for latency_ms_avg"
    assert "✅" in lines[0]


def test_metric_cost_aud_defaults_ok():
    cur = {**CURRENT_RUN, "totals": {"cost_aud_total": 150.0}}
    base = {**BASELINE_RUN, "totals": {"cost_aud_total": 10.0}}
    md = render_markdown_diff(cur, base)
    lines = [line for line in md.splitlines() if "cost_aud_total" in line]
    assert lines
    assert "✅" in lines[0]


# ---------------------------------------------------------------------------
# Metric only in one side
# ---------------------------------------------------------------------------


def test_metric_in_current_only():
    """A metric present in current but absent from baseline shows — for baseline."""
    cur = {**CURRENT_RUN, "totals": {"new_metric": 0.99}}
    base = {**BASELINE_RUN, "totals": {}}
    md = render_markdown_diff(cur, base)
    lines = [line for line in md.splitlines() if "new_metric" in line]
    assert lines
    # baseline column should be em-dash
    assert "—" in lines[0]


def test_metric_in_baseline_only():
    """A metric present in baseline but absent from current shows — for current."""
    cur = {**CURRENT_RUN, "totals": {}}
    base = {**BASELINE_RUN, "totals": {"old_metric": 0.88}}
    md = render_markdown_diff(cur, base)
    lines = [line for line in md.splitlines() if "old_metric" in line]
    assert lines
    assert "—" in lines[0]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_totals_no_baseline():
    cur = {**CURRENT_RUN, "totals": {}}
    md = render_markdown_diff(cur, None)
    assert "| Metric | Current | Status |" in md


def test_empty_totals_with_baseline():
    cur = {**CURRENT_RUN, "totals": {}}
    base = {**BASELINE_RUN, "totals": {}}
    md = render_markdown_diff(cur, base)
    assert "| Metric | Current | Baseline | Δ | Status |" in md


def test_output_ends_with_newline():
    md = render_markdown_diff(CURRENT_RUN, None)
    assert md.endswith("\n")

    md2 = render_markdown_diff(CURRENT_RUN, BASELINE_RUN)
    assert md2.endswith("\n")
