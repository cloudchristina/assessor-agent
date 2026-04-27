"""Per-rule counterfactual generators.

Each function returns (base_rows, mutated_rows, rule_id_targeted).

Design:
- base_rows:    a list of UAR row dicts that fires the targeted rule exactly once.
- mutated_rows: same list with ONE attribute flipped to break that rule.
- Assertion:    running the rules engine on mutated_rows produces fewer findings
                of that rule than on base_rows, AND counts of OTHER rules are unchanged.

Name-safety notes
-----------------
R6 regex (abbreviated): ``^(admin|...|svc[_-].*|app[_-].*|...|root)$``
Any login_name used in base_rows must NOT match that pattern (unless testing R6).
- "svc_etl"  -> matches svc[_-].* -> fires R6; replaced with "etl_batch" in R3 generator.
- "alice_admin", "dormant_admin", "orphan_acct", "explicit_user" → safe.
- "svc_app"  → matches svc[_-].* → intentionally fires R6 in cf_r6.
- "alice_appuser" → safe (not starting with any pattern prefix).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

_NOW = datetime(2026, 4, 25)


def _base_row(login_name: str = "alice", **overrides) -> dict:
    """Clean base row that fires NO rules.  Use overrides to fire a specific rule."""
    row: dict = {
        "login_name": login_name,
        "login_type": "WINDOWS_LOGIN",
        "login_create_date": datetime(2024, 1, 1),
        "last_active_date": _NOW - timedelta(days=10),
        "server_roles": [],
        "database": "appdb (sql01)",
        "mapped_user_name": login_name,
        "user_type": "USER",
        "default_schema": "dbo",
        "db_roles": ["db_datareader"],
        "explicit_read": False,
        "explicit_write": False,
        "explicit_exec": False,
        "explicit_admin": False,
        "access_level": "ReadOnly",
        "grant_counts": {},
        "deny_counts": {},
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# R1: SQL_LOGIN + Admin
# ---------------------------------------------------------------------------

def cf_r1() -> tuple[list[dict], list[dict], str]:
    """R1 fires when SQL_LOGIN + Admin.  Flip login_type to WINDOWS_LOGIN to suppress."""
    base = [_base_row("alice_admin", login_type="SQL_LOGIN", access_level="Admin")]
    mutated = deepcopy(base)
    mutated[0]["login_type"] = "WINDOWS_LOGIN"
    return base, mutated, "R1"


# ---------------------------------------------------------------------------
# R2: dormant privileged account
# ---------------------------------------------------------------------------

def cf_r2() -> tuple[list[dict], list[dict], str]:
    """R2 fires when admin + no recent activity.

    Base: access_level=Admin, last_active_date=None, login_create_date well past the
    90-day cutoff (2020-01-01).  R2 fires because last_active_date is None and
    login_create_date < cutoff.

    Mutated: set last_active_date to 10 days ago → R2 does not fire.
    """
    base = [
        _base_row(
            "dormant_admin",
            access_level="Admin",
            login_create_date=datetime(2020, 1, 1),
            last_active_date=None,
        )
    ]
    mutated = deepcopy(base)
    mutated[0]["last_active_date"] = _NOW - timedelta(days=10)
    return base, mutated, "R2"


# ---------------------------------------------------------------------------
# R3: SoD breach — same principal privileged in dev + prod
# ---------------------------------------------------------------------------

def cf_r3() -> tuple[list[dict], list[dict], str]:
    """R3 fires when same principal holds Admin in both a *dev* and a *prod* database.

    Principal name "etl_batch" does not match the R6 shared-account regex.
    Base: two rows — appdb_dev and appdb_prod → R3 fires.
    Mutated: change prod row's database to appdb_test (classified as "uat") → R3 does
    not fire because the principal is no longer in both dev AND prod.

    last_active_date is set to 10 days ago (recent) so R2 does not fire even though
    access_level is Admin.
    """
    base = [
        _base_row(
            "etl_batch",
            access_level="Admin",
            database="appdb_dev (sql01)",
            last_active_date=_NOW - timedelta(days=10),
        ),
        _base_row(
            "etl_batch",
            access_level="Admin",
            database="appdb_prod (sql01)",
            last_active_date=_NOW - timedelta(days=10),
        ),
    ]
    mutated = deepcopy(base)
    # "appdb_test" → _classify_env returns "uat" → no dev+prod overlap → R3 silent
    mutated[1]["database"] = "appdb_test (sql01)"
    return base, mutated, "R3"


# ---------------------------------------------------------------------------
# R4: orphaned login — mapped_user_name empty for all rows
# ---------------------------------------------------------------------------

def cf_r4() -> tuple[list[dict], list[dict], str]:
    """R4 fires when mapped_user_name is None/empty across all rows for a principal.

    Base: mapped_user_name=None → R4 fires.
    Mutated: set mapped_user_name to the login_name → R4 does not fire.

    "orphan_acct" does not match R6 regex.  access_level=ReadOnly so no R2 risk.
    """
    base = [_base_row("orphan_acct", mapped_user_name=None)]
    mutated = deepcopy(base)
    mutated[0]["mapped_user_name"] = "orphan_acct"
    return base, mutated, "R4"


# ---------------------------------------------------------------------------
# R5: RBAC bypass — explicit permission grants with no role memberships
# ---------------------------------------------------------------------------

def cf_r5() -> tuple[list[dict], list[dict], str]:
    """R5 fires when any explicit_* flag is True AND db_roles is empty.

    Base: explicit_write=True, db_roles=[] → R5 fires.
    Mutated: explicit_write=False → no explicit flag set → R5 does not fire.

    "explicit_user" does not match R6 regex.  access_level=ReadOnly (not Admin) so
    no R1/R2 risk; mapped_user_name defaults to login_name so no R4 risk.
    """
    base = [
        _base_row(
            "explicit_user",
            explicit_write=True,
            db_roles=[],
            access_level="ReadOnly",
        )
    ]
    mutated = deepcopy(base)
    mutated[0]["explicit_write"] = False
    return base, mutated, "R5"


# ---------------------------------------------------------------------------
# R6: shared / generic account naming
# ---------------------------------------------------------------------------

def cf_r6() -> tuple[list[dict], list[dict], str]:
    """R6 fires when login_name matches the shared-account pattern.

    Base: login_name="svc_app" matches svc[_-].* → R6 fires.
    Mutated: rename to "alice_appuser" (does not match any pattern prefix) → R6 silent.

    "svc_app" has access_level=ReadOnly, login_type=WINDOWS_LOGIN, mapped_user_name
    set to the same name and explicit_* all False — so no other rule fires.
    """
    base = [_base_row("svc_app", mapped_user_name="svc_app")]
    mutated = deepcopy(base)
    mutated[0]["login_name"] = "alice_appuser"
    mutated[0]["mapped_user_name"] = "alice_appuser"
    return base, mutated, "R6"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GENERATORS = [cf_r1, cf_r2, cf_r3, cf_r4, cf_r5, cf_r6]
