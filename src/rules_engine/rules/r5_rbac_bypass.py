"""R5: RBAC bypass — explicit grants outside any role (ISM-0445)."""
from __future__ import annotations
from typing import Iterable
from src.shared.models import Finding, UARRow
from src.rules_engine.rules.base import Rule, RuleContext


class R5RbacBypass(Rule):
    rule_id = "R5"
    severity = "HIGH"
    ism_controls = ["ISM-0445"]
    description = "Explicit permission grants to a principal with no role memberships"

    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        out: list[Finding] = []
        for row in rows:
            has_explicit = (
                row.explicit_read
                or row.explicit_write
                or row.explicit_exec
                or row.explicit_admin
            )
            if has_explicit and not row.db_roles:
                out.append(Finding(
                    finding_id="placeholder",
                    run_id=ctx.run_id, rule_id=self.rule_id, severity=self.severity,  # type: ignore[arg-type]
                    ism_controls=list(self.ism_controls),
                    principal=row.login_name,
                    databases=[row.database],
                    evidence={
                        "explicit_read": row.explicit_read,
                        "explicit_write": row.explicit_write,
                        "explicit_exec": row.explicit_exec,
                        "explicit_admin": row.explicit_admin,
                        "db_roles": list(row.db_roles),
                    },
                    detected_at=ctx.now,  # type: ignore[arg-type]
                ))
        return out
