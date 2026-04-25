"""Pure functions for summarising SQL Server permissions and deriving an
access level. No boto3 / pymssql imports — safe to exercise in unit tests."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
from typing import Any


READ_PERMS = {"SELECT"}
WRITE_PERMS = {"INSERT", "UPDATE", "DELETE", "MERGE"}
EXEC_PERMS = {"EXECUTE"}
ADMIN_PERMS = {"ALTER", "CONTROL", "TAKE OWNERSHIP"}


def summarize_permissions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse raw GRANT/DENY rows into a summary with per-state counters and
    booleans indicating explicit read/write/exec/admin privileges."""
    counter: Counter[str] = Counter()
    grants: set[str] = set()
    denies: set[str] = set()
    for r in rows:
        state = (r.get("StateDesc") or "").upper()
        perm = (r.get("Permission") or "").upper()
        if not state or not perm:
            continue
        counter[f"{state}:{perm}"] += 1
        if state == "GRANT":
            grants.add(perm)
        elif state == "DENY":
            denies.add(perm)
    return {
        "perm_counter": counter,
        "grants": grants,
        "denies": denies,
        "explicit_read": any(p in grants for p in READ_PERMS),
        "explicit_write": any(p in grants for p in WRITE_PERMS),
        "explicit_exec": any(p in grants for p in EXEC_PERMS),
        "explicit_admin": any(p in grants for p in ADMIN_PERMS),
    }


def derive_access_level(
    server_roles: list[str],
    db_roles: list[str],
    perm_summary: dict[str, Any],
) -> str:
    """Collapse roles + explicit perms into one of Admin/Write/ReadOnly/Unknown."""
    if any(r.lower() == "sysadmin" for r in server_roles):
        return "Admin"
    role_set = {r.lower() for r in db_roles}
    if "db_owner" in role_set or perm_summary.get("explicit_admin"):
        return "Admin"
    if "db_datawriter" in role_set or perm_summary.get("explicit_write"):
        return "Write"
    if "db_datareader" in role_set or perm_summary.get("explicit_read"):
        return "ReadOnly"
    return "Unknown"


def sid_hex(sid: Any) -> str | None:
    """Hex-encode a SID returned by pymssql as bytes; None otherwise."""
    return sid.hex() if isinstance(sid, (bytes, bytearray)) else None


def fmt_dt(val: Any) -> str:
    """Format a datetime as 'YYYY-MM-DD HH:MM:SS'; return 'N/A' for missing."""
    if val is None or val == "N/A":
        return "N/A"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)
