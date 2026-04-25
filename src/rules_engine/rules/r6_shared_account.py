"""R6: Shared / generic account naming (ISM-1545)."""
from __future__ import annotations
import re
from typing import Iterable
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


# Extended from plan: the plan regex used `svc[_-]` but the stated test case
# `svc_etl` is a prefix match, not exact. Suffixes `.*` added so prefix
# patterns match the documented test cases.
_DEFAULT_REGEX = (
    r"^(admin|administrator|dba\d*|svc[_-].*|app[_-].*|prod[_-].*|sa|test|user\d+|backup|root)$"
)


class R6SharedAccount(Rule):
    rule_id = "R6"
    severity = "HIGH"
    ism_controls = ["ISM-1545"]
    description = "Shared/generic account name indicates non-attributable access"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        pattern_src = str(ctx.config.get("shared_account_regex", _DEFAULT_REGEX))
        pattern = re.compile(pattern_src, re.IGNORECASE)
        seen: set[str] = set()
        out: list[Finding] = []
        principal_rows: dict[str, list[UARRow]] = {}
        for row in rows:
            principal_rows.setdefault(row.login_name, []).append(row)
        for principal, hits in principal_rows.items():
            if principal in seen:
                continue
            if pattern.match(principal):
                seen.add(principal)
                out.append(Finding(
                    finding_id="placeholder",
                    run_id=ctx.run_id, rule_id=self.rule_id, severity=self.severity,  # type: ignore[arg-type]
                    ism_controls=list(self.ism_controls),
                    principal=principal,
                    databases=sorted({h.database for h in hits}),
                    evidence={
                        "matched_pattern": pattern_src,
                        "login_name": principal,
                    },
                    detected_at=ctx.now,  # type: ignore[arg-type]
                ))
        return out
