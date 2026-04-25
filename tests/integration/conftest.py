"""Shared moto fixtures for integration tests."""
from __future__ import annotations
import json
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws():
    """Enter a single moto scope around the test body."""
    with mock_aws():
        yield


@pytest.fixture
def runs_bucket(aws, monkeypatch):
    bucket = "runs-bucket-test"
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    monkeypatch.setenv("RUNS_BUCKET", bucket)
    return bucket


@pytest.fixture
def sql_secret_arn(aws, monkeypatch):
    sm = boto3.client("secretsmanager", region_name="ap-southeast-2")
    payload = {
        "host": "s1",
        "port": "1433",
        "username": "u",
        "password": "p",
        "databases": "appdb",
    }
    arn = sm.create_secret(Name="sql/s1", SecretString=json.dumps(payload))["ARN"]
    monkeypatch.setenv("SECRETS_MANAGER_ARNS", json.dumps([arn]))
    return arn
