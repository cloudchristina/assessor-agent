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


def _row_full(name, login_type, access_level):
    return UARRow(
        login_name=name, login_type=login_type,
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database="db1 (s1)", mapped_user_name=None,
        user_type=None, default_schema=None, db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level=access_level,
        grant_counts={}, deny_counts={},
    )


def test_engine_runs_all_six_rules_on_synthetic_dataset():
    from src.rules_engine.rules import RULES

    rows = [_row_full("admin", login_type="SQL_LOGIN", access_level="Admin")]
    out = run_rules(rows=rows, run_id="run_test", rules=RULES)
    rule_ids = {f.rule_id for f in out.findings}
    assert "R1" in rule_ids
    assert "R6" in rule_ids
    assert all(f.finding_id.startswith("F-run_test-") for f in out.findings)
    assert len({f.finding_id for f in out.findings}) == len(out.findings)
