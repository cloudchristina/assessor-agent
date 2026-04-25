"""R2: Dormant privileged account (ISM-1509 / 1555)."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


class R2DormantAdmin(Rule):
    rule_id = "R2"
    severity = "CRITICAL"
    ism_controls = ["ISM-1509", "ISM-1555"]
    description = "Privileged account inactive beyond threshold"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        threshold = int(ctx.config.get("dormant_days", 90))  # type: ignore[arg-type]
        cutoff: datetime = ctx.now - timedelta(days=threshold)  # type: ignore[operator]
        per: dict[str, list[UARRow]] = defaultdict(list)
        for row in rows:
            if row.access_level != "Admin":
                continue
            if row.last_active_date is None:
                if row.login_create_date < cutoff:
                    per[row.login_name].append(row)
            elif row.last_active_date < cutoff:
                per[row.login_name].append(row)
        out: list[Finding] = []
        for principal, hits in per.items():
            last = max((h.last_active_date for h in hits if h.last_active_date), default=None)
            days = (ctx.now - last).days if last else None  # type: ignore[operator]
            out.append(Finding(
                finding_id="placeholder",
                run_id=ctx.run_id, rule_id=self.rule_id, severity=self.severity,  # type: ignore[arg-type]
                ism_controls=list(self.ism_controls),
                principal=principal,
                databases=sorted({h.database for h in hits}),
                evidence={
                    "last_active_date": last.isoformat() if last else None,
                    "days_since_active": days if days is not None else (ctx.now - hits[0].login_create_date).days,  # type: ignore[operator]
                    "threshold_days": threshold,
                },
                detected_at=ctx.now,  # type: ignore[arg-type]
            ))
        return out
