"""Synthetic golden-case generator. Each scenario builds a CSV + JSON spec.

Scenarios:
  synth_500_principals    500 rows; broad rule coverage
  synth_boundary_89d      principals exactly at 89-day boundary (R2 must NOT fire)
  synth_boundary_91d      principals exactly at 91-day boundary (R2 MUST fire)
  synth_dup_sids          two logins sharing mapped_user_name (R6 fires on generic names)
  synth_high_explicit     20 rows with explicit grants outside roles (R5 x20)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.extract_uar.csv_codec import encode_row
from src.rules_engine.engine import run_rules
from src.rules_engine.rules import RULES
from src.shared.models import UARRow

SCENARIOS: dict[str, object] = {}  # name -> generator function

# Use a fixed reference date for reproducible scenarios. Boundary scenarios
# (synth_boundary_89d / _91d) compute offsets from _NOW so they remain
# accurate relative to the rules engine, which also uses the real wall clock.
# We pin _NOW to match the rules engine's datetime.now() at generation time;
# callers may override per-scenario if a truly fixed date is needed.
_NOW = datetime(2026, 4, 25)
_CREATE_DATE = datetime(2024, 1, 1)


def scenario(name: str):  # type: ignore[no-untyped-def]
    """Decorator to register a scenario generator by name."""

    def deco(fn):  # type: ignore[no-untyped-def]
        SCENARIOS[name] = fn
        return fn

    return deco


def _row(
    login_name: str,
    login_type: str,
    access_level: str,
    last_active: datetime | None,
    *,
    db_roles: list[str] | None = None,
    explicit_write: bool = False,
    explicit_read: bool = False,
    explicit_exec: bool = False,
    explicit_admin: bool = False,
    mapped_user_name: str | None = None,
    database: str = "appdb (sql01)",
    login_create_date: datetime | None = None,
) -> dict:
    """Build a raw row dict compatible with UARRow.model_validate()."""
    if db_roles is None:
        db_roles = ["db_datareader"]
    return {
        "login_name": login_name,
        "login_type": login_type,
        "login_create_date": login_create_date or _CREATE_DATE,
        "last_active_date": last_active,
        "server_roles": [],
        "database": database,
        "mapped_user_name": mapped_user_name if mapped_user_name is not None else login_name,
        "user_type": "USER",
        "default_schema": "dbo",
        "db_roles": db_roles,
        "explicit_read": explicit_read,
        "explicit_write": explicit_write,
        "explicit_exec": explicit_exec,
        "explicit_admin": explicit_admin,
        "access_level": access_level,
        "grant_counts": {},
        "deny_counts": {},
    }


@scenario("synth_500_principals")
def gen_500(seed: int = 42) -> list[dict]:
    """500 rows with broad rule coverage.

    Breakdown:
      i < 25  : svc_etl_N  SQL_LOGIN Admin  (active)   → R1 x25, R6 x25
      i < 40  : old_admin_N WINDOWS_LOGIN Admin dormant 120d → R2 x15
      i < 50  : app_N  WINDOWS_LOGIN ReadOnly recent      → R6 x10
      i >= 50 : user_NNN WINDOWS_LOGIN ReadOnly random    → clean
    Total expected findings far exceeds 50 (R1 x25 + R2 x15 + R6 x35 = 75+).
    """
    random.seed(seed)
    rows: list[dict] = []
    for i in range(500):
        if i < 25:
            # R1: SQL_LOGIN + Admin → plus R6 because name matches svc_ pattern
            rows.append(
                _row(
                    f"svc_etl_{i}",
                    "SQL_LOGIN",
                    "Admin",
                    _NOW - timedelta(days=10),
                )
            )
        elif i < 40:
            # R2: WINDOWS_LOGIN Admin dormant 120 days (> 90d threshold)
            rows.append(
                _row(
                    f"old_admin_{i}",
                    "WINDOWS_LOGIN",
                    "Admin",
                    _NOW - timedelta(days=120),
                )
            )
        elif i < 50:
            # R6: app_ prefix matches shared-account regex
            rows.append(
                _row(
                    f"app_{i}",
                    "WINDOWS_LOGIN",
                    "ReadOnly",
                    _NOW - timedelta(days=5),
                )
            )
        else:
            rows.append(
                _row(
                    f"user_{i:03d}",
                    "WINDOWS_LOGIN",
                    "ReadOnly",
                    _NOW - timedelta(days=random.randint(1, 60)),  # noqa: S311
                )
            )
    return rows


@scenario("synth_boundary_89d")
def gen_boundary_89d() -> list[dict]:
    """5 Admin WINDOWS_LOGIN rows with last_active exactly 89 days ago (wall clock).

    The rules engine uses datetime.now(utc) as its reference, so we must
    compute offsets from the real current time, not the fixed _NOW constant.
    At threshold=90 days, last_active = now - 89d means the principal has been
    inactive for 89 days, which is < 90, so R2 must NOT fire.
    This stress-tests the rule's strict-less-than boundary (row.last_active_date < cutoff).
    """
    wall_now = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []
    for i in range(5):
        rows.append(
            _row(
                f"boundary_admin_{i}",
                "WINDOWS_LOGIN",
                "Admin",
                wall_now - timedelta(days=89),
                login_create_date=wall_now - timedelta(days=400),
            )
        )
    return rows


@scenario("synth_boundary_91d")
def gen_boundary_91d() -> list[dict]:
    """5 Admin WINDOWS_LOGIN rows with last_active exactly 91 days ago (wall clock).

    The rules engine uses datetime.now(utc) as its reference, so we must
    compute offsets from the real current time, not the fixed _NOW constant.
    At threshold=90 days, last_active = now - 91d means 91d > 90d, so R2
    MUST fire for each principal.
    This stress-tests the rule's strictly-greater-than boundary.
    """
    wall_now = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []
    for i in range(5):
        rows.append(
            _row(
                f"boundary_admin_{i}",
                "WINDOWS_LOGIN",
                "Admin",
                wall_now - timedelta(days=91),
                login_create_date=wall_now - timedelta(days=400),
            )
        )
    return rows


@scenario("synth_dup_sids")
def gen_dup_sids() -> list[dict]:
    """Two distinct logins that share the same mapped_user_name ('shared_svc_user').

    Design choice: both logins are named with the svc_ prefix so R6 fires on
    each. The shared mapped_user_name is included as evidence but R6 fires
    on the login_name regex match, not the mapping itself.  This scenario
    validates that deduplication in the rules engine doesn't collapse distinct
    logins that happen to map to the same DB user — both R6 findings must be
    present, one per login_name.
    """
    shared_db_user = "shared_svc_user"
    rows: list[dict] = [
        _row(
            "svc_app_alpha",
            "WINDOWS_LOGIN",
            "ReadOnly",
            _NOW - timedelta(days=3),
            mapped_user_name=shared_db_user,
        ),
        _row(
            "svc_app_beta",
            "WINDOWS_LOGIN",
            "ReadOnly",
            _NOW - timedelta(days=3),
            mapped_user_name=shared_db_user,
        ),
        # Add a few clean rows so the scenario is non-trivial
        _row(
            "normal_user_01",
            "WINDOWS_LOGIN",
            "ReadOnly",
            _NOW - timedelta(days=10),
        ),
        _row(
            "normal_user_02",
            "WINDOWS_LOGIN",
            "ReadOnly",
            _NOW - timedelta(days=7),
        ),
    ]
    return rows


@scenario("synth_high_explicit")
def gen_high_explicit() -> list[dict]:
    """20 rows each with explicit_write=True and empty db_roles → R5 x20.

    R5 fires when a row has any explicit permission AND no role memberships.
    This scenario validates that R5 scales correctly under load and that each
    row generates exactly one finding (R5 is per-row, not per-principal).
    """
    rows: list[dict] = []
    for i in range(20):
        rows.append(
            _row(
                f"explicit_user_{i:02d}",
                "WINDOWS_LOGIN",
                "Write",
                _NOW - timedelta(days=random.randint(1, 30)),  # noqa: S311
                db_roles=[],  # no roles — triggers R5
                explicit_write=True,
            )
        )
    return rows


def write_outputs(
    scenario_name: str,
    rows: list[dict],
    out_csv: Path,
    out_json: Path,
) -> None:
    """Write the CSV rows and the JSON spec for the given scenario."""
    fieldnames = list(rows[0].keys())
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(encode_row(r))

    typed = [UARRow.model_validate(r) for r in rows]
    out = run_rules(typed, run_id=scenario_name, rules=RULES)
    spec = {
        "case_id": scenario_name,
        "input_csv": str(out_csv).replace(str(Path.cwd()) + "/", ""),
        "expected_findings": [
            {
                "rule_id": f.rule_id,
                "principal": f.principal,
                "severity": f.severity,
            }
            for f in out.findings
        ],
        "expected_counts": {r.rule_id: out.summary.get(r.rule_id, 0) for r in RULES},
        "must_mention": [],
        "must_not_mention": [],
        "notes": (
            f"Synthetic case generated by scripts/generate_golden.py"
            f" --scenario={scenario_name}"
        ),
    }
    out_json.write_text(json.dumps(spec, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a synthetic golden eval case (CSV + JSON spec)."
    )
    ap.add_argument("--scenario", required=True, choices=list(SCENARIOS))
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--out-json", required=True, type=Path)
    args = ap.parse_args()

    generator = SCENARIOS[args.scenario]
    rows = generator()  # type: ignore[operator]
    write_outputs(args.scenario, rows, args.out_csv, args.out_json)
    print(
        f"wrote {args.out_csv} ({len(rows)} rows) and {args.out_json}"
    )


if __name__ == "__main__":
    main()
