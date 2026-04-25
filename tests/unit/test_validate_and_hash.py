import json
from datetime import datetime
import boto3
import pytest
from moto import mock_aws
from src.extract_uar.csv_writer import build_csv_and_manifest
from src.validate_and_hash.handler import lambda_handler


def _row(login: str, db: str = "appdb (s1)") -> dict:
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


def _setup_buckets(csv_bytes: bytes, manifest_json: str):
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(Bucket="test-bucket-123", Key="raw/uar.csv", Body=csv_bytes)
    s3.put_object(Bucket="test-bucket-123", Key="raw/manifest.json", Body=manifest_json)
    return s3


def _event():
    return {
        "csv_s3_uri": "s3://test-bucket-123/raw/uar.csv",
        "manifest_s3_uri": "s3://test-bucket-123/raw/manifest.json",
        "bucket": "test-bucket-123",
    }


@mock_aws
def test_validates_round_tripped_extract():
    rows = [_row("alice"), _row("bob")]
    csv_bytes, manifest = build_csv_and_manifest(
        rows, run_id="run_x", servers=["s1"], databases=["appdb"], cadence="weekly"
    )
    _setup_buckets(csv_bytes, manifest.model_dump_json())
    out = lambda_handler(_event(), None)
    assert out["run_id"] == "run_x"
    assert out["cadence"] == "weekly"
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    body = s3.get_object(Bucket="test-bucket-123", Key="validated/run_x.json")["Body"].read()
    payload = json.loads(body)
    assert payload["run_id"] == "run_x"
    assert len(payload["rows"]) == 2


@mock_aws
def test_raises_on_hash_mismatch():
    rows = [_row("alice")]
    csv_bytes, manifest = build_csv_and_manifest(
        rows, run_id="run_x", servers=["s1"], databases=["appdb"], cadence="weekly"
    )
    tampered = manifest.model_copy(update={"row_ids_sha256": "0" * 64})
    _setup_buckets(csv_bytes, tampered.model_dump_json())
    with pytest.raises(RuntimeError, match="manifest_hash_mismatch"):
        lambda_handler(_event(), None)


@mock_aws
def test_raises_on_schema_violation():
    """Tamper a CSV cell to a value Pydantic will reject."""
    rows = [_row("alice")]
    csv_bytes, manifest = build_csv_and_manifest(
        rows, run_id="run_x", servers=["s1"], databases=["appdb"], cadence="weekly"
    )
    bad_csv = csv_bytes.replace(b"SQL_LOGIN", b"INVALID_TYPE")
    _setup_buckets(bad_csv, manifest.model_dump_json())
    with pytest.raises(Exception):
        lambda_handler(_event(), None)
