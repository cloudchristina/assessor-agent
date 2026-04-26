"""Tests for evals/adversarial/fixtures/10k_findings_gen.py generator."""
from __future__ import annotations

import csv
from evals.adversarial.fixtures.gen_10k_findings import generate


def test_generate_10k_smoke_test_with_100_rows(tmp_path):
    """Smoke test: generate 100 rows (smaller for speed), verify CSV structure."""
    out_csv = tmp_path / "test_100rows.csv"
    result = generate(out_csv, count=100)

    assert out_csv.exists(), "CSV file was not created"
    assert result["rows_written"] == 100
    assert result["expected_findings_min"] == 200  # R5 + R6 per row

    # Verify header and row count
    with out_csv.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 100, f"Expected 100 rows, got {len(rows)}"

    # Verify header fields match expected UAR schema
    expected_fields = {
        "login_name",
        "login_type",
        "login_create_date",
        "last_active_date",
        "server_roles",
        "database",
        "mapped_user_name",
        "user_type",
        "default_schema",
        "db_roles",
        "explicit_read",
        "explicit_write",
        "explicit_exec",
        "explicit_admin",
        "access_level",
        "grant_counts",
        "deny_counts",
    }
    assert set(rows[0].keys()) == expected_fields

    # Verify each row has R6-matching login name (svc_app_*)
    for i, row in enumerate(rows):
        assert row["login_name"] == f"svc_app_{i:05d}"
        assert row["login_type"] == "WINDOWS_LOGIN"
        assert row["database"] == "appdb (sql01)"
        assert row["db_roles"] == ""  # Empty, to trigger R5
        assert row["explicit_write"] == "True"  # To trigger R5
        assert row["access_level"] == "Write"
