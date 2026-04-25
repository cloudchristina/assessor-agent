"""End-to-end integration tests for the refactored extractor Lambda."""
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
import boto3
import pytest

from src.extract_uar import handler as h


MINIMAL_SYNTH_CSV = (
    "login_name,login_type,login_create_date,last_active_date,server_roles,"
    "database,mapped_user_name,user_type,default_schema,db_roles,"
    "explicit_read,explicit_write,explicit_exec,explicit_admin,access_level,"
    "grant_counts,deny_counts\n"
    "alice,SQL_LOGIN,2024-01-01 00:00:00,,,"
    "appdb (s1),,,,,"
    "False,False,False,True,Admin,"
    "SELECT=1,\n"
)


def _put_fixture(bucket: str, key: str, body: bytes) -> str:
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.put_object(Bucket=bucket, Key=key, Body=body)
    return f"s3://{bucket}/{key}"


def test_synthetic_path_writes_csv_and_manifest(runs_bucket, monkeypatch):
    uri = _put_fixture(runs_bucket, "fixtures/synth.csv", MINIMAL_SYNTH_CSV.encode("utf-8"))
    monkeypatch.setenv("SYNTHETIC_DATA_S3_URI", uri)

    result = h.lambda_handler(
        {"cadence": "weekly", "started_at": "2026-04-25T09:00:00+10:00"},
        None,
    )

    assert result["run_id"] == "run_2026-04-25_weekly"
    assert result["bucket"] == runs_bucket
    assert result["csv_s3_uri"].endswith("raw/dt=2026-04-25/cadence=weekly/uar.csv")
    assert result["manifest_s3_uri"].endswith("raw/dt=2026-04-25/cadence=weekly/manifest.json")

    s3 = boto3.client("s3", region_name="ap-southeast-2")
    manifest = json.loads(
        s3.get_object(Bucket=runs_bucket, Key="raw/dt=2026-04-25/cadence=weekly/manifest.json")["Body"].read()
    )
    assert manifest["row_count"] == 1
    assert manifest["cadence"] == "weekly"
    assert len(manifest["row_ids_sha256"]) == 64


def test_missing_secrets_env_var_raises(runs_bucket, monkeypatch):
    monkeypatch.delenv("SECRETS_MANAGER_ARNS", raising=False)
    monkeypatch.delenv("SYNTHETIC_DATA_S3_URI", raising=False)

    with pytest.raises(RuntimeError, match="SECRETS_MANAGER_ARNS"):
        h.lambda_handler({"cadence": "weekly"}, None)


def test_unreachable_server_fails_the_run(runs_bucket, sql_secret_arn, monkeypatch):
    monkeypatch.delenv("SYNTHETIC_DATA_S3_URI", raising=False)

    def _boom(**_kw):
        raise ConnectionError("simulated unreachable host")

    with patch("src.extract_uar.handler.get_connection", side_effect=_boom):
        with pytest.raises(RuntimeError, match="extract-uar failures"):
            h.lambda_handler(
                {"cadence": "weekly", "started_at": "2026-04-25T09:00:00+10:00"},
                None,
            )


def test_live_path_happy_case_with_mocked_pymssql(runs_bucket, sql_secret_arn, monkeypatch):
    """One server, one DB, one mapped login returning a single admin row."""
    monkeypatch.delenv("SYNTHETIC_DATA_S3_URI", raising=False)

    server_rows = {
        "server_logins": [{
            "PrincipalId": 1, "LoginName": "alice", "LoginType": "SQL_LOGIN",
            "IsDisabled": 0, "LoginCreateDate": None, "ModifyDate": None,
            "LoginSid": b"\x01",
        }],
        "server_role_members": [],
        "last_active": [],
    }
    db_rows = {
        "db_users": [{
            "UserName": "alice", "UserType": "SQL_USER", "AuthType": "INSTANCE",
            "CreateDate": None, "ModifyDate": None, "DefaultSchema": "dbo",
            "UserSid": b"\x01",
        }],
        "db_role_members": [{"UserName": "alice", "RoleName": "db_owner"}],
        "db_permissions": [],
    }

    def _fake_cursor(rows_for_sequence: list[list[dict]]):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.__iter__ = lambda self: iter(rows_for_sequence.pop(0))
        return cur

    def _fake_connect(database=None, **_kwargs):
        conn = MagicMock()
        if database is None:
            queued = [server_rows["server_logins"], server_rows["server_role_members"], server_rows["last_active"]]
        else:
            queued = [db_rows["db_users"], db_rows["db_role_members"], db_rows["db_permissions"]]
        conn.cursor.return_value = _fake_cursor(queued)
        return conn

    with patch("src.extract_uar.handler.get_connection", side_effect=_fake_connect):
        result = h.lambda_handler(
            {"cadence": "weekly", "started_at": "2026-04-25T09:00:00+10:00"},
            None,
        )

    assert result["run_id"] == "run_2026-04-25_weekly"
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    manifest = json.loads(
        s3.get_object(Bucket=runs_bucket, Key="raw/dt=2026-04-25/cadence=weekly/manifest.json")["Body"].read()
    )
    assert manifest["row_count"] == 1
