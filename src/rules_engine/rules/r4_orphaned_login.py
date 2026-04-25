"""R4: Orphaned login — no DB mapping across any row (ISM-1555)."""
from __future__ import annotations
from collections import defaultdict
from typing import Iterable
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


class R4OrphanedLogin(Rule):
    rule_id = "R4"
    severity = "HIGH"
    ism_controls = ["ISM-1555"]
    description = "Login present but never mapped to a database user"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        per: dict[str, list[UARRow]] = defaultdict(list)
        for row in rows:
            per[row.login_name].append(row)
        out: list[Finding] = []
        for principal, hits in per.items():
            if all((h.mapped_user_name is None or h.mapped_user_name == "") for h in hits):
                out.append(Finding(
                    finding_id="placeholder",
                    run_id=ctx.run_id, rule_id=self.rule_id, severity=self.severity,  # type: ignore[arg-type]
                    ism_controls=list(self.ism_controls),
                    principal=principal,
                    databases=sorted({h.database for h in hits}),
                    evidence={
                        "row_count": len(hits),
                        "all_unmapped": True,
                    },
                    detected_at=ctx.now,  # type: ignore[arg-type]
                ))
        return out
