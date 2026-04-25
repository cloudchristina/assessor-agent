from datetime import datetime
from src.shared.models import UARRow
from src.rules_engine.rules.r6_shared_account import R6SharedAccount
from src.rules_engine.rules.base import RuleContext


def _row(name):
    return UARRow(
        login_name=name, login_type="SQL_LOGIN",
        login_create_date=datetime(2024, 1, 1), last_active_date=None,
        server_roles=[], database="db1 (s1)", mapped_user_name=None,
        user_type=None, default_schema=None, db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level="Unknown",
        grant_counts={}, deny_counts={},
    )


def _ctx(config=None):
    return RuleContext(run_id="r", now=datetime(2026, 4, 25), config=config or {})


def test_fires_on_admin():
    findings = R6SharedAccount().evaluate([_row("admin")], _ctx())
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "ISM-1545" in findings[0].ism_controls


def test_fires_on_svc_prefix():
    findings = R6SharedAccount().evaluate([_row("svc_etl")], _ctx())
    assert len(findings) == 1


def test_does_not_fire_on_personal_name():
    findings = R6SharedAccount().evaluate([_row("alice.smith")], _ctx())
    assert findings == []


def test_fires_on_generic_user_number():
    findings = R6SharedAccount().evaluate([_row("user12")], _ctx())
    assert len(findings) == 1


def test_regex_is_configurable_via_context():
    # Override with a regex that only matches foo-prefixed names
    ctx = _ctx(config={"shared_account_regex": r"^foo.*$"})
    rule = R6SharedAccount()
    assert rule.evaluate([_row("foo_x")], ctx) != []
    assert rule.evaluate([_row("admin")], ctx) == []
