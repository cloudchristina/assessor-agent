"""Iterate rules, assign deterministic finding IDs."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from src.shared.models import Finding, RulesEngineOutput, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


def run_rules(rows: list[UARRow], run_id: str, rules: list[Rule]) -> RulesEngineOutput:
    # Naive UTC so comparisons against UARRow datetimes (also naive) don't raise.
    ctx = RuleContext(run_id=run_id, now=datetime.now(timezone.utc).replace(tzinfo=None))
    all_findings: list[Finding] = []
    for r in rules:
        raw = r.evaluate(rows, ctx)
        for idx, f in enumerate(raw):
            assigned_id = f"F-{run_id}-{r.rule_id}-{idx:04d}"
            all_findings.append(f.model_copy(update={"finding_id": assigned_id}))
    summary = _summarise(all_findings, rules)
    return RulesEngineOutput(
        run_id=run_id,
        findings=all_findings,
        summary=summary,
        principals_scanned=len({r.login_name for r in rows}),
        databases_scanned=len({r.database for r in rows}),
    )


def _summarise(findings: list[Finding], rules: list[Rule]) -> dict[str, int]:
    out: dict[str, int] = {r.rule_id: 0 for r in rules}
    sev = Counter(f.severity for f in findings)
    for f in findings:
        out[f.rule_id] = out.get(f.rule_id, 0) + 1
    out.update({k: v for k, v in sev.items()})
    return out
