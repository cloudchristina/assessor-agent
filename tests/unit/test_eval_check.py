"""Tests for eval_check.py CI gate (Task 4.5)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts import eval_check
from scripts.eval_check import check, main


class TestThresholdFor:
    """Test _threshold_for helper — metric name resolution."""

    def test_exact_match(self):
        """faithfulness in THRESHOLDS → return it."""
        th = eval_check._threshold_for("faithfulness")  # type: ignore[attr-defined]
        assert th is not None
        assert th["fail"] == 0.85
        assert th["warn"] == 0.92

    def test_avg_suffix_stripped(self):
        """faithfulness_avg → strip _avg, find faithfulness → return."""
        th = eval_check._threshold_for("faithfulness_avg")
        assert th is not None
        assert th["fail"] == 0.85
        assert th["warn"] == 0.92

    def test_precision_avg(self):
        """precision_avg is directly in THRESHOLDS."""
        th = eval_check._threshold_for("precision_avg")
        assert th is not None
        assert th["fail"] == 0.90
        assert th["warn"] == 0.95

    def test_unknown_metric(self):
        """latency_ms → no threshold → return None."""
        th = eval_check._threshold_for("latency_ms")
        assert th is None

    def test_unknown_metric_with_avg_suffix(self):
        """latency_ms_avg → strip _avg, still not found → return None."""
        th = eval_check._threshold_for("latency_ms_avg")
        assert th is None


class TestCheck:
    """Test check() pure function — the core logic."""

    def test_check_passes_when_all_metrics_above_warn(self):
        """All metrics above warn threshold → exit 0, all ✅."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.95,
                "answer_relevance_avg": 0.90,
                "context_precision_avg": 0.90,
                "bertscore_f1_avg": 0.85,
                "precision_avg": 0.96,
                "recall_avg": 0.96,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        assert all("✅" in ln for ln in lines)
        assert not any("❌" in ln for ln in lines)

    def test_check_fails_when_metric_below_fail_threshold(self):
        """faithfulness_avg=0.5 < 0.85 fail → exit 1, ❌."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.5,
                "answer_relevance_avg": 0.90,
            }
        }
        code, lines = check(eval_run)
        assert code == 1
        # Find faithfulness line
        faith_lines = [ln for ln in lines if "faithfulness" in ln]
        assert len(faith_lines) == 1
        assert "❌" in faith_lines[0]
        assert "0.5000" in faith_lines[0]
        assert "0.8500" in faith_lines[0]

    def test_check_warns_but_passes_when_metric_in_warn_zone(self):
        """faithfulness_avg=0.86 between fail 0.85 and warn 0.92 → exit 0, ⚠️."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.86,
                "answer_relevance_avg": 0.90,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        faith_lines = [ln for ln in lines if "faithfulness" in ln]
        assert len(faith_lines) == 1
        assert "⚠️" in faith_lines[0]
        assert "0.8600" in faith_lines[0]
        assert "0.9200" in faith_lines[0]

    def test_check_skips_unknown_metrics(self):
        """latency_ms_avg=1500 → no threshold → ✅, code=0."""
        eval_run: dict[str, Any] = {
            "totals": {
                "latency_ms_avg": 1500,
                "faithfulness_avg": 0.95,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        latency_lines = [ln for ln in lines if "latency_ms" in ln]
        assert len(latency_lines) == 1
        assert "✅" in latency_lines[0]
        assert "(no threshold)" in latency_lines[0]

    def test_check_multiple_breaches(self):
        """Multiple metrics below fail → exit 1, multiple ❌."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.5,
                "answer_relevance_avg": 0.7,
                "context_precision_avg": 0.95,
            }
        }
        code, lines = check(eval_run)
        assert code == 1
        breaches = [ln for ln in lines if "❌" in ln]
        assert len(breaches) == 2
        assert any("faithfulness" in ln for ln in breaches)
        assert any("answer_relevance" in ln for ln in breaches)

    def test_check_with_non_numeric_metric(self):
        """total_cases="5" (string) → skip it (try/except)."""
        eval_run: dict[str, Any] = {
            "totals": {
                "total_cases": "5",
                "faithfulness_avg": 0.95,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        # Should not crash; faithfulness is ok
        assert any("✅" in ln and "faithfulness" in ln for ln in lines)

    def test_check_empty_totals(self):
        """eval_run with empty totals → exit 0."""
        eval_run: dict[str, Any] = {"totals": {}}
        code, lines = check(eval_run)
        assert code == 0
        assert lines == []

    def test_check_missing_totals_key(self):
        """eval_run missing totals → treat as empty → exit 0."""
        eval_run: dict[str, Any] = {}
        code, lines = check(eval_run)
        assert code == 0
        assert lines == []

    def test_check_sorted_output(self):
        """Lines are sorted by metric name."""
        eval_run: dict[str, Any] = {
            "totals": {
                "z_metric": 0.9,
                "a_metric": 0.9,
                "m_metric": 0.9,
            }
        }
        _, lines = check(eval_run)
        # Extract metric names from lines (between {metric}: and :)
        metrics: list[Any] = []
        for ln in lines:
            parts = ln.split()
            if len(parts) >= 2:
                metrics.append(parts[1].rstrip(":"))
        # Check sorted
        assert metrics == sorted(metrics)

    def test_boundary_fail_threshold(self):
        """Exactly at fail threshold (0.85) → in warn zone (between fail and warn) → ⚠️."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.85,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        assert any("⚠️" in ln for ln in lines)

    def test_boundary_warn_threshold(self):
        """Exactly at warn threshold (0.92) → not < warn, so ✅."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.92,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        assert any("✅" in ln for ln in lines)

    def test_just_below_warn_threshold(self):
        """Just below warn threshold (0.919) → ⚠️."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.919,
            }
        }
        code, lines = check(eval_run)
        assert code == 0
        assert any("⚠️" in ln for ln in lines)


class TestMainWithFile:
    """Test main() CLI with temporary files."""

    def test_main_passes_with_good_json(self, tmp_path: Path):
        """Write good eval_run.json, call main, exit 0."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.95,
                "answer_relevance_avg": 0.90,
            }
        }
        json_file = tmp_path / "eval_run.json"
        json_file.write_text(json.dumps(eval_run))

        old_argv = sys.argv
        try:
            sys.argv = ["eval_check", f"--in={json_file}"]
            code = main()
            assert code == 0
        finally:
            sys.argv = old_argv

    def test_main_fails_with_bad_metrics(self, tmp_path: Path):
        """Write eval_run.json with breaches, call main, exit 1."""
        eval_run: dict[str, Any] = {
            "totals": {
                "faithfulness_avg": 0.5,
                "answer_relevance_avg": 0.90,
            }
        }
        json_file = tmp_path / "eval_run.json"
        json_file.write_text(json.dumps(eval_run))

        old_argv = sys.argv
        try:
            sys.argv = ["eval_check", f"--in={json_file}"]
            code = main()
            assert code == 1
        finally:
            sys.argv = old_argv
