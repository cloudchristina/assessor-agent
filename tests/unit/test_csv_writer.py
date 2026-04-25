from datetime import datetime
from src.extract_uar.csv_writer import build_csv_and_manifest


def _row_dict(login: str, db: str) -> dict:
    return {
        "login_name": login,
        "login_type": "SQL_LOGIN",
        "login_create_date": datetime(2024, 1, 1),
        "last_active_date": None,
        "server_roles": [],
        "database": db,
        "mapped_user_name": None,
        "user_type": None,
        "default_schema": None,
        "db_roles": [],
        "explicit_read": False,
        "explicit_write": False,
        "explicit_exec": False,
        "explicit_admin": False,
        "access_level": "Unknown",
        "grant_counts": {},
        "deny_counts": {},
    }


def test_manifest_hash_is_deterministic():
    rows = [_row_dict("alice", "db1 (s1)")]
    _, m1 = build_csv_and_manifest(rows, run_id="r1", servers=["s1"], databases=["db1"], cadence="weekly")
    _, m2 = build_csv_and_manifest(rows, run_id="r2", servers=["s1"], databases=["db1"], cadence="weekly")
    assert m1.row_ids_sha256 == m2.row_ids_sha256


def test_hash_differs_on_extra_row():
    r1 = [_row_dict("alice", "db1 (s1)")]
    r2 = r1 + [_row_dict("bob", "db1 (s1)")]
    _, m1 = build_csv_and_manifest(r1, run_id="r", servers=["s1"], databases=["db1"], cadence="weekly")
    _, m2 = build_csv_and_manifest(r2, run_id="r", servers=["s1"], databases=["db1"], cadence="weekly")
    assert m1.row_ids_sha256 != m2.row_ids_sha256


def test_hash_invariant_to_row_order():
    a = [_row_dict("alice", "db1 (s1)"), _row_dict("bob", "db2 (s1)")]
    b = list(reversed(a))
    _, m1 = build_csv_and_manifest(a, run_id="r", servers=["s1"], databases=["db1", "db2"], cadence="weekly")
    _, m2 = build_csv_and_manifest(b, run_id="r", servers=["s1"], databases=["db1", "db2"], cadence="weekly")
    assert m1.row_ids_sha256 == m2.row_ids_sha256


def test_csv_bytes_round_trip_through_codec():
    import csv
    import io
    from src.extract_uar.csv_codec import decode_row

    rows = [_row_dict("alice", "db1 (s1)")]
    csv_bytes, manifest = build_csv_and_manifest(
        rows, run_id="r", servers=["s1"], databases=["db1"], cadence="weekly"
    )
    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    decoded = [decode_row(r) for r in reader]
    assert len(decoded) == 1
    assert decoded[0]["login_name"] == "alice"
    assert decoded[0]["database"] == "db1 (s1)"
    assert manifest.row_count == 1
