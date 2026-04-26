"""CI gate: exit 1 if any eval-totals metric breaches its fail threshold.

Reads `eval_run.json` (the file written by scripts/eval_run.py) and applies
thresholds from src.eval_harness.reporter.THRESHOLDS.

Usage: python -m scripts.eval_check --in=eval_run.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.eval_harness.reporter import THRESHOLDS


def _threshold_for(metric: str) -> dict[str, float] | None:
    """Look up a threshold by metric name; tries metric exactly then strips _avg suffix."""
    if metric in THRESHOLDS:
        return THRESHOLDS[metric]
    if metric.endswith("_avg"):
        bare = metric[:-len("_avg")]
        if bare in THRESHOLDS:
            return THRESHOLDS[bare]
    return None


def check(eval_run: dict[str, Any]) -> tuple[int, list[str]]:
    """Returns (exit_code, lines_to_print).

    Checks each metric in eval_run["totals"] against its threshold:
    - If value < fail_threshold: record breach (❌), exit code = 1
    - If value < warn_threshold: record warning (⚠️), but exit code = 0
    - Else: record ok (✅)

    Parameters
    ----------
    eval_run : dict[str, Any]
        Dict with "totals" key containing metric name → value mappings.

    Returns
    -------
    (exit_code, lines) where:
    - exit_code: 0 if no breaches, 1 if any metric < fail threshold
    - lines: list of formatted status strings, one per metric
    """
    totals: dict[str, Any] = eval_run.get("totals", {})
    lines: list[str] = []
    fail = False

    for metric in sorted(totals.keys()):
        th = _threshold_for(metric)
        val = totals[metric]

        # Try to convert to float; skip if not numeric
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue

        if th is None:
            lines.append(f"  ✅ {metric}: {v:.4f} (no threshold)")
            continue

        if v < th["fail"]:
            lines.append(
                f"  ❌ {metric}: {v:.4f} < fail threshold {th['fail']:.4f}"
            )
            fail = True
        elif v < th["warn"]:
            lines.append(
                f"  ⚠️  {metric}: {v:.4f} below warn threshold {th['warn']:.4f}"
            )
        else:
            lines.append(f"  ✅ {metric}: {v:.4f}")

    return (1 if fail else 0, lines)


def main() -> int:
    """CLI entrypoint.

    Reads --in (path to eval_run.json), checks thresholds, prints summary,
    returns exit code 0 or 1.
    """
    ap = argparse.ArgumentParser(
        description="CI gate: check eval metrics against thresholds"
    )
    ap.add_argument(
        "--in",
        dest="input",
        required=True,
        type=Path,
        help="Path to eval_run.json",
    )
    args = ap.parse_args()

    eval_run = json.loads(args.input.read_text())
    code, lines = check(eval_run)

    print(f"eval_check {args.input.name}:")
    for ln in lines:
        print(ln)
    print(f"\nexit code: {code}")

    return code


if __name__ == "__main__":
    sys.exit(main())
