"""R3: Segregation-of-duties breach — same principal privileged in DEV + PROD (ISM-1175)."""
from __future__ import annotations
from collections import defaultdict
from typing import Iterable, Literal
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


_PRIV_ROLES = {"db_owner", "sysadmin"}


def _classify_env(database: str) -> Literal["dev", "prod", "uat", "other"]:
    low = database.lower()
    if "prod" in low:
        return "prod"
    if "dev" in low:
        return "dev"
    if "uat" in low:
        return "uat"
    return "other"


def _is_privileged(row: UARRow) -> bool:
    if row.access_level == "Admin":
        return True
    return any(r.lower() in _PRIV_ROLES for r in row.db_roles)


class R3SodBreach(Rule):
    rule_id = "R3"
    severity = "HIGH"
    ism_controls = ["ISM-1175"]
    description = "Same principal holds privileged access across DEV and PROD environments"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        per: dict[str, dict[str, list[UARRow]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            if not _is_privileged(row):
                continue
            env = _classify_env(row.database)
            if env == "other":
                continue
            per[row.login_name][env].append(row)
        out: list[Finding] = []
        for principal, by_env in per.items():
            if "dev" in by_env and "prod" in by_env:
                hits = by_env["dev"] + by_env["prod"]
                out.append(Finding(
                    finding_id="placeholder",
                    run_id=ctx.run_id, rule_id=self.rule_id, severity=self.severity,  # type: ignore[arg-type]
                    ism_controls=list(self.ism_controls),
                    principal=principal,
                    databases=sorted({h.database for h in hits}),
                    evidence={
                        "dev_databases": sorted({h.database for h in by_env["dev"]}),
                        "prod_databases": sorted({h.database for h in by_env["prod"]}),
                    },
                    detected_at=ctx.now,  # type: ignore[arg-type]
                ))
        return out
