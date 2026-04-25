from datetime import datetime
from src.shared.models import UARRow, RulesEngineOutput
from src.rules_engine.engine import run_rules
from src.rules_engine.rules.base import Rule


class _NoopRule(Rule):
    rule_id = "R1"
    severity = "CRITICAL"
    ism_controls = ["ISM-1546"]
    description = "noop"

    def evaluate(self, rows, ctx):
        return []


def _row(name="alice"):
    return UARRow(
        login_name=name, login_type="SQL_LOGIN",
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database="db1 (s1)", mapped_user_name=None,
        user_type=None, default_schema=None, db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level="Unknown",
        grant_counts={}, deny_counts={},
    )


def test_engine_returns_zero_findings_with_noop_rule():
    out = run_rules(rows=[_row()], run_id="run_x", rules=[_NoopRule()])
    assert isinstance(out, RulesEngineOutput)
    assert out.findings == []
    assert out.principals_scanned == 1
