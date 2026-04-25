import json
import boto3
from moto import mock_aws
from src.reconciliation_gate.handler import lambda_handler


def _put(s3, bucket, findings, narrative):
    s3.put_object(Bucket=bucket, Key="findings.json", Body=json.dumps({"findings": findings}))
    s3.put_object(Bucket=bucket, Key="narrative.json", Body=json.dumps(narrative))


def _setup():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    return s3


def _event():
    return {
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
    }


def _ref(fid):
    return {"finding_id": fid, "group_theme": None, "remediation": "x", "ism_citation": "ISM-1"}


@mock_aws
def test_passes_when_counts_and_sets_match():
    s3 = _setup()
    findings = [{"finding_id": "F-1"}, {"finding_id": "F-2"}]
    narrative = {"total_findings": 2, "finding_narratives": [_ref("F-1"), _ref("F-2")]}
    _put(s3, "test-bucket-123", findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is True
    assert out["passed_int"] == 1
    assert out["reasons"] == []


@mock_aws
def test_fails_on_count_mismatch():
    s3 = _setup()
    findings = [{"finding_id": "F-1"}, {"finding_id": "F-2"}, {"finding_id": "F-3"}, {"finding_id": "F-4"}]
    narrative = {"total_findings": 5, "finding_narratives": [_ref(f"F-{i}") for i in range(1, 5)]}
    _put(s3, "test-bucket-123", findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert out["passed_int"] == 0
    assert "count_mismatch" in out["reasons"]


@mock_aws
def test_fails_on_set_mismatch():
    s3 = _setup()
    findings = [{"finding_id": "F-1"}, {"finding_id": "F-2"}]
    narrative = {"total_findings": 2, "finding_narratives": [_ref("F-1"), _ref("F-FAKE")]}
    _put(s3, "test-bucket-123", findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert out["passed_int"] == 0
    assert "set_mismatch" in out["reasons"]
