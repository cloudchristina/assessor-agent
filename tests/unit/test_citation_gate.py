import json
import boto3
from moto import mock_aws
from src.citation_gate.handler import lambda_handler


@mock_aws
def test_passes_when_all_cited_ids_exist():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    findings = {"findings": [{
        "finding_id": "F-1", "rule_id": "R1", "severity": "CRITICAL",
        "run_id": "run_x", "ism_controls": ["ISM-1546"],
        "principal": "alice", "databases": ["db1"], "evidence": {},
        "detected_at": "2026-04-25T00:00:00",
    }]}
    narrative = {"finding_narratives": [{
        "finding_id": "F-1", "group_theme": None,
        "remediation": "x", "ism_citation": "ISM-1546",
    }]}
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps(findings))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps(narrative))
    out = lambda_handler({
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
    }, None)
    assert out["passed"] is True
    assert out["passed_int"] == 1
    assert out["missing_ids"] == []


@mock_aws
def test_fails_when_narrative_invents_id():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    findings = {"findings": []}
    narrative = {"finding_narratives": [{
        "finding_id": "F-FAKE", "group_theme": None,
        "remediation": "x", "ism_citation": "ISM-1546",
    }]}
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps(findings))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps(narrative))
    out = lambda_handler({
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
    }, None)
    assert out["passed"] is False
    assert out["passed_int"] == 0
    assert "F-FAKE" in out["missing_ids"]
