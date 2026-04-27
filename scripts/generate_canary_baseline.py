"""Generate a canary baseline JSON for a given fixture CSV.

Runs the deterministic rules engine against the fixture and records
per-rule finding counts + total findings.  Judge/faithfulness scores are
placeholder (0.90) because they require a live AWS Bedrock call; re-run
after deploying to replace them with real values.

CLI
---
    python scripts/generate_canary_baseline.py \\
        --fixture evals/canary/fixtures/month_2025-11.csv \\
        --out     evals/canary/baselines/month_2025-11.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure repo root is on the path when run as a script.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.extract_uar.csv_codec import decode_row  # noqa: E402
from src.rules_engine.engine import run_rules  # noqa: E402
from src.rules_engine.rules import RULES  # noqa: E402
from src.shared.models import UARRow  # noqa: E402

_RULE_IDS = [r.rule_id for r in RULES]
_PLACEHOLDER_JUDGE = 0.90
_TOLERANCE_JUDGE = 0.05


def _extract_month(fixture_path: Path) -> str:
    """Best-effort month from a filename like month_2025-11.csv → '2025-11'."""
    m = re.search(r"(\d{4}-\d{2})", fixture_path.stem)
    return m.group(1) if m else fixture_path.stem


def run_fixture(fixture_path: Path) -> dict:
    """Load fixture CSV, run rules engine, return baseline metrics dict."""
    rows: list[UARRow] = []
    with fixture_path.open(newline="") as fh:
        for raw in csv.DictReader(fh):
            rows.append(UARRow.model_validate(decode_row(raw)))

    month = _extract_month(fixture_path)
    out = run_rules(rows, run_id=f"canary-baseline-{month}", rules=RULES)

    per_rule_counts: dict[str, int] = dict.fromkeys(_RULE_IDS, 0)
    for finding in out.findings:
        per_rule_counts[finding.rule_id] = per_rule_counts.get(finding.rule_id, 0) + 1

    # Store fixture path relative to the repo root for portability.
    try:
        rel_fixture = str(fixture_path.relative_to(_ROOT))
    except ValueError:
        rel_fixture = str(fixture_path)

    return {
        "month": month,
        "fixture": rel_fixture,
        "expected_metrics": {
            "total_findings": len(out.findings),
            "per_rule_counts": per_rule_counts,
            "judge_faithfulness": _PLACEHOLDER_JUDGE,
            "judge_completeness": _PLACEHOLDER_JUDGE,
        },
        "tolerance": {
            "judge_faithfulness": _TOLERANCE_JUDGE,
            "judge_completeness": _TOLERANCE_JUDGE,
        },
        "notes": (
            f"Baseline established {datetime.now(UTC).strftime('%Y-%m-%d')} "
            "by scripts/generate_canary_baseline.py. "
            "judge_faithfulness and judge_completeness are PLACEHOLDERS (0.90) "
            "because live judge scores require AWS Bedrock. "
            "Re-run generate_canary_baseline.py --update-judge after a live deploy "
            "to replace placeholders with real values."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate canary baseline JSON from a fixture CSV."
    )
    ap.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="Path to the canary fixture CSV (e.g. evals/canary/fixtures/month_2025-11.csv)",
    )
    ap.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for the baseline JSON (e.g. evals/canary/baselines/month_2025-11.json)",
    )
    args = ap.parse_args()

    fixture_path = args.fixture.resolve()
    if not fixture_path.exists():
        print(f"ERROR: fixture not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    baseline = run_fixture(fixture_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(baseline, indent=2))

    counts = baseline["expected_metrics"]["per_rule_counts"]
    total = baseline["expected_metrics"]["total_findings"]
    fired = {k: v for k, v in counts.items() if v > 0}
    print(f"wrote {args.out}  |  total_findings={total}  fired={fired}")


if __name__ == "__main__":
    main()
