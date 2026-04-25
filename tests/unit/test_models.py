from datetime import datetime
import pytest
from pydantic import ValidationError
from src.shared.models import UARRow, ExtractManifest


def test_uar_row_accepts_minimal_valid():
    row = UARRow(
        login_name="alice",
        login_type="SQL_LOGIN",
        login_create_date=datetime(2024, 1, 1),
        last_active_date=None,
        server_roles=[],
        database="appdb (sql01)",
        mapped_user_name=None,
        user_type=None,
        default_schema=None,
        db_roles=[],
        explicit_read=False,
        explicit_write=False,
        explicit_exec=False,
        explicit_admin=False,
        access_level="Unknown",
        grant_counts={},
        deny_counts={},
    )
    assert row.login_name == "alice"


def test_uar_row_rejects_unknown_login_type():
    with pytest.raises(ValidationError):
        UARRow.model_validate({
            "login_name": "alice",
            "login_type": "INVALID",
            "login_create_date": "2024-01-01T00:00:00",
            "last_active_date": None,
            "server_roles": [],
            "database": "x",
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
        })


def test_extract_manifest_round_trip():
    m = ExtractManifest(
        run_id="run_2026-04-25_weekly",
        cadence="weekly",
        extracted_at=datetime(2026, 4, 25, 9, 0),
        extractor_version="0.1.0",
        servers_processed=["sql01"],
        databases_processed=["appdb"],
        row_count=10,
        row_ids_sha256="0" * 64,
        schema_version="1",
    )
    assert m.model_dump_json()
    assert ExtractManifest.model_validate_json(m.model_dump_json()) == m
