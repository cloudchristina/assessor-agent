from datetime import datetime
from src.shared.models import UARRow
from src.rules_engine.rules.r5_rbac_bypass import R5RbacBypass
from src.rules_engine.rules.base import RuleContext


def _row(
    name="alice",
    database="db1 (s1)",
    db_roles=None,
    explicit_read=False,
    explicit_write=False,
    explicit_exec=False,
    explicit_admin=False,
):
    return UARRow(
        login_name=name, login_type="WINDOWS_LOGIN",
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database=database, mapped_user_name=name,
        user_type="USER", default_schema="dbo", db_roles=db_roles or [],
        explicit_read=explicit_read, explicit_write=explicit_write,
        explicit_exec=explicit_exec, explicit_admin=explicit_admin,
        access_level="Unknown",
        grant_counts={}, deny_counts={},
    )


def _ctx():
    return RuleContext(run_id="r", now=datetime(2026, 4, 25))


def test_fires_when_explicit_admin_without_role():
    findings = R5RbacBypass().evaluate([_row(explicit_admin=True)], _ctx())
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "ISM-0445" in findings[0].ism_controls


def test_does_not_fire_when_explicit_read_with_role():
    findings = R5RbacBypass().evaluate(
        [_row(explicit_read=True, db_roles=["db_datareader"])],
        _ctx(),
    )
    assert findings == []


def test_does_not_fire_when_no_explicit_flags():
    findings = R5RbacBypass().evaluate([_row()], _ctx())
    assert findings == []


def test_one_finding_per_principal_database_pair():
    rows = [
        _row(database="db1 (s1)", explicit_write=True),
        _row(database="db2 (s1)", explicit_write=True),
    ]
    findings = R5RbacBypass().evaluate(rows, _ctx())
    assert len(findings) == 2
    assert {f.databases[0] for f in findings} == {"db1 (s1)", "db2 (s1)"}
