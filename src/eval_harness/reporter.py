"""Render eval-run metric diffs as markdown for PR comments.

Spec §3.3 thresholds — edit the THRESHOLDS dict below to adjust.
Metrics absent from the dict default to ✅ (no threshold applies).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Spec §3.3 thresholds
# Keys match the *metric name* as it appears in the `totals` dict.
# For avg-suffixed keys (e.g. "faithfulness_avg") the lookup strips "_avg"
# so a single threshold entry covers both bare and avg-suffixed names.
# ---------------------------------------------------------------------------
THRESHOLDS: dict[str, dict[str, float]] = {
    "faithfulness": {"fail": 0.85, "warn": 0.92},
    "answer_relevance": {"fail": 0.80, "warn": 0.88},
    "context_precision": {"fail": 0.80, "warn": 0.88},
    "bertscore_f1": {"fail": 0.70, "warn": 0.80},
    "precision_avg": {"fail": 0.90, "warn": 0.95},
    "recall_avg": {"fail": 0.90, "warn": 0.95},
}


def _lookup_threshold(metric: str) -> dict[str, float] | None:
    """Return threshold dict for *metric*, checking both bare and _avg-stripped forms."""
    if metric in THRESHOLDS:
        return THRESHOLDS[metric]
    # Strip trailing "_avg" and try again (e.g. "faithfulness_avg" → "faithfulness")
    if metric.endswith("_avg"):
        bare = metric[:-4]
        if bare in THRESHOLDS:
            return THRESHOLDS[bare]
    return None


def _status_for(metric: str, value: float | None) -> str:
    """Return ✅ / ⚠️ / ❌ / — for *metric* at *value* given §3.3 thresholds."""
    if value is None:
        return "—"
    th = _lookup_threshold(metric)
    if th is None:
        return "✅"
    if value < th["fail"]:
        return "❌"
    if value < th["warn"]:
        return "⚠️"
    return "✅"


def _fmt(v: Any) -> str:
    """Format a metric value for display."""
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{float(v):.4f}"
    return str(v)


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def render_markdown_diff(current_run: dict, baseline_run: dict | None) -> str:
    """Produce a markdown report comparing *current_run* totals to *baseline_run* totals.

    If *baseline_run* is None (first run on branch), renders a 3-column table
    (Metric | Current | Status) with a note that no baseline is available.

    Otherwise renders a 5-column table
    (Metric | Current | Baseline | Δ | Status).
    """
    cur_totals: dict[str, Any] = current_run.get("totals", {})
    out: list[str] = ["## Eval metric diff", ""]
    out.append(
        f"- Current: `{current_run.get('eval_run_id', '?')}` "
        f"({current_run.get('cases_run', 0)} cases, suite={current_run.get('suite', '?')})"
    )

    if baseline_run is None:
        out.append("- Baseline: _none — first run on this branch_")
        out.append("")
        out.append("| Metric | Current | Status |")
        out.append("|---|---|---|")
        for k in sorted(cur_totals.keys()):
            v = cur_totals[k]
            out.append(f"| `{k}` | {_fmt(v)} | {_status_for(k, _as_float(v))} |")
        return "\n".join(out) + "\n"

    base_totals: dict[str, Any] = baseline_run.get("totals", {})
    out.append(f"- Baseline: `{baseline_run.get('eval_run_id', '?')}`")
    out.append("")
    out.append("| Metric | Current | Baseline | Δ | Status |")
    out.append("|---|---|---|---|---|")
    keys = sorted(set(cur_totals) | set(base_totals))
    for k in keys:
        cur_raw = cur_totals.get(k)
        base_raw = base_totals.get(k)
        cur_f = _as_float(cur_raw)
        base_f = _as_float(base_raw)
        if cur_f is None or base_f is None:
            delta_str = "—"
        else:
            delta_str = f"{cur_f - base_f:+.4f}"
        status = _status_for(k, cur_f)
        out.append(
            f"| `{k}` | {_fmt(cur_raw)} | {_fmt(base_raw)} | {delta_str} | {status} |"
        )
    return "\n".join(out) + "\n"


def _cli() -> None:
    from src.eval_harness.ddb_writer import load_baseline_for_branch

    ap = argparse.ArgumentParser(
        description="Render eval metric diff markdown for a PR comment."
    )
    ap.add_argument("--in", dest="input", required=True, type=Path,
                    help="Path to current eval_run.json")
    ap.add_argument(
        "--baseline",
        default="main",
        help="Branch name to compare against (looks up most-recent eval_run from DDB)",
    )
    args = ap.parse_args()
    current = json.loads(args.input.read_text())
    baseline = load_baseline_for_branch(args.baseline)  # may be None for first run
    sys.stdout.write(render_markdown_diff(current, baseline))


if __name__ == "__main__":
    _cli()
