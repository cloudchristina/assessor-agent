import json
import os
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("FINDINGS_TABLE", "findings")
    monkeypatch.setenv("RUNS_BUCKET", "runs")


@mock_aws
def test_get_finding_reads_from_ddb(_env):
    from src.agent_narrator.tools import get_finding

    ddb = boto3.resource("dynamodb", region_name="ap-southeast-2")
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
    ddb.Table("findings").put_item(Item={
        "run_id": "run_x",
        "finding_id": "F-1",
        "rule_id": "R1",
        "severity": "CRITICAL",
    })
    out = get_finding(run_id="run_x", finding_id="F-1")
    assert out["finding_id"] == "F-1"
    assert out["severity"] == "CRITICAL"


def test_get_ism_control_returns_catalogue_entry():
    from src.agent_narrator.tools import get_ism_control

    out = get_ism_control(control_id="ISM-1546")
    assert out["control_id"] == "ISM-1546"
    assert "MFA" in out["title"] or "MFA" in out["intent"]


def test_get_rule_spec_returns_metadata():
    from src.agent_narrator.tools import get_rule_spec

    out = get_rule_spec(rule_id="R1")
    assert out["rule_id"] == "R1"
    assert out["severity"] == "CRITICAL"
    assert "ISM-1546" in out["ism_controls"]


def test_get_rule_spec_raises_on_unknown_rule():
    from src.agent_narrator.tools import get_rule_spec

    with pytest.raises(KeyError):
        get_rule_spec(rule_id="R99")


@mock_aws
def test_get_prior_cycle_summary_reads_from_s3(_env):
    from src.agent_narrator.tools import get_prior_cycle_summary

    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="runs",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(
        Bucket="runs",
        Key="rules/run_prev/findings.json",
        Body=json.dumps({"run_id": "run_prev", "findings": [], "summary": {}}).encode(),
    )
    out = get_prior_cycle_summary(prior_run_id="run_prev")
    assert out["run_id"] == "run_prev"
