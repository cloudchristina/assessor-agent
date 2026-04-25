import json
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("RUNS_TABLE", "runs")
    monkeypatch.setenv("FINDINGS_TABLE", "findings")


def _setup(s3, ddb):
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    ddb.create_table(
        TableName="runs",
        KeySchema=[{"AttributeName": "run_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "run_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()
    ddb.create_table(
        TableName="findings",
        KeySchema=[
            {"AttributeName": "run_id", "KeyType": "HASH"},
            {"AttributeName": "finding_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "run_id", "AttributeType": "S"},
            {"AttributeName": "finding_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    ).wait_until_exists()


def _findings_doc():
    return {"findings": [
        {
            "finding_id": "F-1", "run_id": "run_x", "rule_id": "R1",
            "severity": "CRITICAL", "ism_controls": ["ISM-1546"],
            "principal": "alice", "databases": ["appdb"], "evidence": {},
            "detected_at": "2026-04-25T00:00:00",
        },
    ]}


def _narrative_doc():
    return {"finding_narratives": [
        {"finding_id": "F-1", "group_theme": "SQL login admin",
         "remediation": "Disable SQL login", "ism_citation": "ISM-1546"},
    ]}


@mock_aws
def test_publish_writes_runs_and_findings_rows(_env):
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _setup(s3, ddb)
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps(_findings_doc()))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps(_narrative_doc()))

    from src.publish_triage.handler import lambda_handler
    result = lambda_handler({
        "run_id": "run_x",
        "cadence": "weekly",
        "started_at": "2026-04-25T09:00:00+10:00",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "all_gates_passed": True,
        "manifest": {"row_ids_sha256": "abc", "row_count": 10},
        "judge_score": {"faithfulness": 0.95},
        "gates": {"citation": True, "reconciliation": True, "judge": True},
        "trace_id": "t-1",
    }, None)

    assert result["findings_count"] == 1
    run = ddb.Table("runs").get_item(Key={"run_id": "run_x"})["Item"]
    assert run["status"] == "succeeded"
    assert run["rows_scanned"] == 10

    finding = ddb.Table("findings").get_item(Key={"run_id": "run_x", "finding_id": "F-1"})["Item"]
    assert finding["remediation"] == "Disable SQL login"
    assert finding["review"] == {"status": "pending"}


@mock_aws
def test_publish_marks_quarantined_when_gates_fail(_env):
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
    _setup(s3, ddb)
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps({"findings": []}))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps({"finding_narratives": []}))

    from src.publish_triage.handler import lambda_handler
    lambda_handler({
        "run_id": "run_q",
        "cadence": "weekly",
        "started_at": "2026-04-25T09:00:00+10:00",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "all_gates_passed": False,
        "manifest": {"row_ids_sha256": "abc", "row_count": 0},
        "judge_score": {"faithfulness": 0.0},
        "gates": {},
    }, None)

    run = ddb.Table("runs").get_item(Key={"run_id": "run_q"})["Item"]
    assert run["status"] == "quarantined"
