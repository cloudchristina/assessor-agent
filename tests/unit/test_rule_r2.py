from datetime import datetime, timedelta
from src.shared.models import UARRow
from src.rules_engine.rules.r2_dormant_admin import R2DormantAdmin
from src.rules_engine.rules.base import RuleContext


def _row(name, last_active, access="Admin"):
    return UARRow(
        login_name=name, login_type="WINDOWS_LOGIN",
        login_create_date=datetime(2020, 1, 1), last_active_date=last_active,
        server_roles=[], database="db1 (s1)", mapped_user_name="alice",
        user_type="USER", default_schema="dbo", db_roles=[],
        explicit_read=False, explicit_write=False, explicit_exec=False,
        explicit_admin=False, access_level=access,
        grant_counts={}, deny_counts={},
    )


NOW = datetime(2026, 4, 25)


def _ctx():
    return RuleContext(run_id="r", now=NOW, config={"dormant_days": 90})


def test_fires_on_admin_dormant_91d():
    findings = R2DormantAdmin().evaluate([_row("alice", NOW - timedelta(days=91))], _ctx())
    assert len(findings) == 1
    assert findings[0].evidence["days_since_active"] >= 91


def test_does_not_fire_on_admin_active_yesterday():
    findings = R2DormantAdmin().evaluate([_row("bob", NOW - timedelta(days=1))], _ctx())
    assert findings == []


def test_does_not_fire_on_readonly_dormant():
    findings = R2DormantAdmin().evaluate([_row("carol", NOW - timedelta(days=200), "ReadOnly")], _ctx())
    assert findings == []


def test_fires_on_admin_never_logged_in_account_older_than_30d():
    r = _row("dave", None)
    r2 = r.model_copy(update={"login_create_date": NOW - timedelta(days=200)})
    findings = R2DormantAdmin().evaluate([r2], _ctx())
    assert len(findings) == 1
    assert findings[0].evidence["last_active_date"] is None


def test_uses_config_threshold():
    ctx = RuleContext(run_id="r", now=NOW, config={"dormant_days": 30})
    findings = R2DormantAdmin().evaluate([_row("alice", NOW - timedelta(days=45))], ctx)
    assert len(findings) == 1
