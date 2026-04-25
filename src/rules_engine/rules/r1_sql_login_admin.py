"""R1: SQL login with Admin access (ISM-1546)."""
from __future__ import annotations
from collections import defaultdict
from typing import Iterable
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


class R1SqlLoginAdmin(Rule):
    rule_id = "R1"
    severity = "CRITICAL"
    ism_controls = ["ISM-1546"]
    description = "SQL login with Admin access cannot enforce MFA"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        per_principal: dict[str, list[UARRow]] = defaultdict(list)
        for row in rows:
            if row.login_type == "SQL_LOGIN" and row.access_level == "Admin":
                per_principal[row.login_name].append(row)
        out: list[Finding] = []
        for principal, hits in per_principal.items():
            out.append(Finding(
                finding_id="placeholder",  # engine reassigns
                run_id=ctx.run_id,
                rule_id=self.rule_id,
                severity=self.severity,  # type: ignore[arg-type]
                ism_controls=list(self.ism_controls),
                principal=principal,
                databases=sorted({h.database for h in hits}),
                evidence={
                    "login_type": "SQL_LOGIN",
                    "access_levels": sorted({h.access_level for h in hits}),
                    "row_count": len(hits),
                },
                detected_at=ctx.now,  # type: ignore[arg-type]
            ))
        return out
