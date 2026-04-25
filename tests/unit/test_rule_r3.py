from datetime import datetime
from src.shared.models import UARRow
from src.rules_engine.rules.r3_sod_breach import R3SodBreach
from src.rules_engine.rules.base import RuleContext


def _row(name, database, access_level="Admin", db_roles=None):
    return UARRow(
        login_name=name, login_type="WINDOWS_LOGIN",
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database=database, mapped_user_name=name,
        user_type="USER", default_schema="dbo", db_roles=db_roles or [],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level=access_level,
        grant_counts={}, deny_counts={},
    )


def _ctx():
    return RuleContext(run_id="r", now=datetime(2026, 4, 25))


def test_fires_when_same_admin_in_dev_and_prod():
    rows = [
        _row("alice", "appdb_dev (s1)"),
        _row("alice", "appdb_prod (s1)"),
    ]
    findings = R3SodBreach().evaluate(rows, _ctx())
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "ISM-1175" in findings[0].ism_controls
    assert findings[0].principal == "alice"


def test_does_not_fire_when_admin_only_in_dev():
    findings = R3SodBreach().evaluate([_row("alice", "appdb_dev (s1)")], _ctx())
    assert findings == []


def test_does_not_fire_when_admin_only_in_prod():
    findings = R3SodBreach().evaluate([_row("alice", "appdb_prod (s1)")], _ctx())
    assert findings == []


def test_does_not_fire_when_different_logins_in_dev_and_prod():
    rows = [
        _row("alice", "appdb_dev (s1)"),
        _row("bob", "appdb_prod (s1)"),
    ]
    findings = R3SodBreach().evaluate(rows, _ctx())
    assert findings == []


def test_fires_when_db_owner_role_in_dev_and_prod():
    rows = [
        _row("alice", "appdb_dev (s1)", access_level="Write", db_roles=["db_owner"]),
        _row("alice", "appdb_prod (s1)", access_level="Write", db_roles=["db_owner"]),
    ]
    findings = R3SodBreach().evaluate(rows, _ctx())
    assert len(findings) == 1


def test_does_not_fire_when_database_has_no_env_tag():
    rows = [
        _row("alice", "randomdb (s1)"),
        _row("alice", "otherdb (s1)"),
    ]
    findings = R3SodBreach().evaluate(rows, _ctx())
    assert findings == []
