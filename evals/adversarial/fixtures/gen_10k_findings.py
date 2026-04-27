"""Inline generator for the 10k-row adversarial volume case.

Wired by adversarial_runner via generator_fn field in 10k_findings.json.
Generates 10,000 rows designed to fire R5 + R6 rules, producing ~20,000 findings.
"""
from __future__ import annotations
import csv
from datetime import datetime, timedelta
from pathlib import Path

from src.extract_uar.csv_codec import encode_row


def generate(out_csv: Path, *, count: int = 10_000, seed: int = 42) -> dict:
    """Write `count` rows to `out_csv`. Each row fires R5 + R6.

    R5 fires when: has_explicit (any of read/write/exec/admin) AND empty db_roles
    R6 fires when: login_name matches shared account pattern (svc_*, app_*, etc.)

    With both rules firing per row, we get 2 findings per row = 20k findings for 10k rows.

    Args:
        out_csv: Path to write CSV fixture to
        count: Number of rows to generate (default 10,000)
        seed: Random seed for reproducibility

    Returns:
        dict with {rows_written, expected_findings_min} for sanity-check
    """
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    now = datetime(2026, 4, 25)
    rows = []

    for i in range(count):
        rows.append({
            "login_name": f"svc_app_{i:05d}",  # Matches R6 pattern: svc_*
            "login_type": "WINDOWS_LOGIN",
            "login_create_date": datetime(2024, 1, 1),
            "last_active_date": now - timedelta(days=10),
            "server_roles": [],
            "database": "appdb (sql01)",
            "mapped_user_name": f"svc_app_{i:05d}",
            "user_type": "USER",
            "default_schema": "dbo",
            "db_roles": [],  # Empty = R5 fires if has_explicit
            "explicit_read": False,
            "explicit_write": True,  # Trigger R5
            "explicit_exec": False,
            "explicit_admin": False,
            "access_level": "Write",
            "grant_counts": {},
            "deny_counts": {},
        })

    fieldnames = list(rows[0].keys())
    with out_csv.open("w") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(encode_row(r))

    return {
        "rows_written": count,
        "expected_findings_min": count * 2,  # R5 + R6 per row
    }
