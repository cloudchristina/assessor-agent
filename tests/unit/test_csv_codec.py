from src.extract_uar.csv_codec import encode_row, decode_row


ROW = {
    "login_name": "alice", "login_type": "SQL_LOGIN",
    "login_create_date": "2024-01-01 00:00:00", "last_active_date": None,
    "server_roles": ["sysadmin", "dbcreator"], "database": "db1 (s1)",
    "mapped_user_name": None, "user_type": None, "default_schema": None,
    "db_roles": [], "explicit_read": False, "explicit_write": False,
    "explicit_exec": False, "explicit_admin": True,
    "access_level": "Admin",
    "grant_counts": {"SELECT": 2, "INSERT": 1},
    "deny_counts": {},
}


def test_round_trip_preserves_data():
    encoded = encode_row(ROW)
    assert encoded["server_roles"] == "dbcreator, sysadmin"
    assert encoded["grant_counts"] == "INSERT=1; SELECT=2"
    assert encoded["explicit_admin"] == "True"
    assert encoded["mapped_user_name"] == ""
    decoded = decode_row(encoded)
    assert decoded["server_roles"] == ["dbcreator", "sysadmin"]
    assert decoded["grant_counts"] == {"INSERT": 1, "SELECT": 2}
    assert decoded["mapped_user_name"] is None
    assert decoded["explicit_admin"] is True
