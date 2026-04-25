from datetime import datetime
from src.extract_uar.access_logic import (
    summarize_permissions,
    derive_access_level,
    sid_hex,
    fmt_dt,
)


def _empty_summary():
    return summarize_permissions([])


def test_summarize_collects_grants_and_denies():
    s = summarize_permissions([
        {"StateDesc": "GRANT", "Permission": "SELECT"},
        {"StateDesc": "GRANT", "Permission": "INSERT"},
        {"StateDesc": "DENY", "Permission": "DELETE"},
    ])
    assert s["explicit_read"] is True
    assert s["explicit_write"] is True
    assert s["explicit_admin"] is False
    assert "DELETE" in s["denies"]
    assert s["perm_counter"]["GRANT:SELECT"] == 1


def test_summarize_skips_blank_rows():
    s = summarize_permissions([
        {"StateDesc": "", "Permission": "SELECT"},
        {"StateDesc": "GRANT", "Permission": ""},
        {},
    ])
    assert s["explicit_read"] is False
    assert s["perm_counter"] == {}


def test_derive_access_sysadmin_is_admin():
    assert derive_access_level(["sysadmin"], [], _empty_summary()) == "Admin"


def test_derive_access_db_owner_is_admin():
    assert derive_access_level([], ["db_owner"], _empty_summary()) == "Admin"


def test_derive_access_db_datawriter_is_write():
    assert derive_access_level([], ["db_datawriter"], _empty_summary()) == "Write"


def test_derive_access_db_datareader_is_readonly():
    assert derive_access_level([], ["db_datareader"], _empty_summary()) == "ReadOnly"


def test_derive_access_default_is_unknown():
    assert derive_access_level([], [], _empty_summary()) == "Unknown"


def test_derive_access_explicit_admin_overrides_default():
    summary = summarize_permissions([{"StateDesc": "GRANT", "Permission": "CONTROL"}])
    assert derive_access_level([], [], summary) == "Admin"


def test_sid_hex_handles_bytes_and_none():
    assert sid_hex(b"\x01\x02\xff") == "0102ff"
    assert sid_hex(None) is None
    assert sid_hex("not-bytes") is None


def test_fmt_dt_handles_datetime_none_and_strings():
    assert fmt_dt(datetime(2026, 4, 25, 9, 0, 0)) == "2026-04-25 09:00:00"
    assert fmt_dt(None) == "N/A"
    assert fmt_dt("N/A") == "N/A"
    assert fmt_dt("2024-01-01") == "2024-01-01"
