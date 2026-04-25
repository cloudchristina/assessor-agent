from datetime import datetime
from src.shared.models import UARRow
from src.rules_engine.rules.r4_orphaned_login import R4OrphanedLogin
from src.rules_engine.rules.base import RuleContext


def _row(name, mapped_user, database="db1 (s1)"):
    return UARRow(
        login_name=name, login_type="WINDOWS_LOGIN",
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database=database, mapped_user_name=mapped_user,
        user_type=None, default_schema=None, db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level="Unknown",
        grant_counts={}, deny_counts={},
    )


def _ctx():
    return RuleContext(run_id="r", now=datetime(2026, 4, 25))


def test_fires_when_all_rows_have_no_mapped_user():
    rows = [
        _row("alice", None, "db1 (s1)"),
        _row("alice", None, "db2 (s1)"),
        _row("alice", None, "db3 (s1)"),
    ]
    findings = R4OrphanedLogin().evaluate(rows, _ctx())
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "ISM-1555" in findings[0].ism_controls
    assert findings[0].principal == "alice"


def test_does_not_fire_when_some_rows_mapped():
    rows = [
        _row("alice", None, "db1 (s1)"),
        _row("alice", "alice", "db2 (s1)"),
        _row("alice", None, "db3 (s1)"),
    ]
    findings = R4OrphanedLogin().evaluate(rows, _ctx())
    assert findings == []


def test_fires_with_single_row_orphan():
    findings = R4OrphanedLogin().evaluate([_row("bob", None)], _ctx())
    assert len(findings) == 1
