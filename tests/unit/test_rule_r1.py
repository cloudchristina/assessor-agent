from datetime import datetime
from src.shared.models import UARRow
from src.rules_engine.rules.r1_sql_login_admin import R1SqlLoginAdmin
from src.rules_engine.rules.base import RuleContext


def _row(name, login_type, access_level):
    return UARRow(
        login_name=name, login_type=login_type,
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database="db1 (s1)", mapped_user_name=None,
        user_type=None, default_schema=None, db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level=access_level,
        grant_counts={}, deny_counts={},
    )


def _ctx():
    return RuleContext(run_id="r", now=datetime(2026, 4, 25))


def test_r1_fires_on_sql_login_admin():
    rule = R1SqlLoginAdmin()
    findings = rule.evaluate([_row("alice", "SQL_LOGIN", "Admin")], _ctx())
    assert len(findings) == 1
    assert findings[0].rule_id == "R1"
    assert findings[0].severity == "CRITICAL"
    assert "ISM-1546" in findings[0].ism_controls
    assert findings[0].principal == "alice"


def test_r1_does_not_fire_on_windows_login_admin():
    rule = R1SqlLoginAdmin()
    findings = rule.evaluate([_row("bob", "WINDOWS_LOGIN", "Admin")], _ctx())
    assert findings == []


def test_r1_does_not_fire_on_sql_login_readonly():
    rule = R1SqlLoginAdmin()
    findings = rule.evaluate([_row("carol", "SQL_LOGIN", "ReadOnly")], _ctx())
    assert findings == []


def test_r1_dedupes_per_principal_across_databases():
    rule = R1SqlLoginAdmin()
    rows = [_row("alice", "SQL_LOGIN", "Admin"), _row("alice", "SQL_LOGIN", "Admin")]
    findings = rule.evaluate(rows, _ctx())
    assert len(findings) == 1
    assert set(findings[0].databases) == {"db1 (s1)"}
