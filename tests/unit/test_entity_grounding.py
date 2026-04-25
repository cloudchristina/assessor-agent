import json
import boto3
from moto import mock_aws
from src.entity_grounding_gate.entity_extraction import extract_entities
from src.entity_grounding_gate.handler import lambda_handler


def test_extracts_principals_from_narrative_text():
    txt = "Login `svc_etl` has admin on `appdb_prod` per ISM-1546."
    e = extract_entities(txt)
    assert "svc_etl" in e["principals"]
    assert "appdb_prod" in e["databases"]
    assert "ISM-1546" in e["controls"]


def test_extracts_dates_and_numbers():
    txt = "12 findings detected on 2026-04-25"
    e = extract_entities(txt)
    assert "2026-04-25" in e["dates"]
    assert 12 in e["numbers"]


def test_handles_empty_narrative():
    e = extract_entities("")
    assert e == {
        "principals": set(),
        "databases": set(),
        "controls": set(),
        "dates": set(),
        "numbers": set(),
    }


def _setup_buckets(findings, narrative):
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps({"findings": findings}))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps(narrative))


def _event():
    return {
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
    }


@mock_aws
def test_grounding_passes_when_entities_match_findings():
    findings = [{
        "finding_id": "F-1", "principal": "alice",
        "databases": ["appdb_prod"], "ism_controls": ["ISM-1546"],
    }]
    narrative = {
        "executive_summary": "Login `alice` flagged on `appdb_prod` per ISM-1546.",
        "theme_clusters": [],
        "finding_narratives": [],
    }
    _setup_buckets(findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is True
    assert out["passed_int"] == 1


@mock_aws
def test_grounding_fails_on_ungrounded_principal():
    findings = [{
        "finding_id": "F-1", "principal": "alice",
        "databases": ["appdb_prod"], "ism_controls": ["ISM-1546"],
    }]
    narrative = {
        "executive_summary": "Login `bob` was also flagged.",
        "theme_clusters": [],
        "finding_narratives": [],
    }
    _setup_buckets(findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert "bob" in out["ungrounded_entities"]["principals"]


@mock_aws
def test_grounding_fails_on_false_negation():
    findings = [{
        "finding_id": "F-1", "principal": "alice",
        "databases": ["appdb_prod"], "ism_controls": ["ISM-1546"],
    }]
    narrative = {
        "executive_summary": "No issues with `appdb_prod` this cycle.",
        "theme_clusters": [],
        "finding_narratives": [],
    }
    _setup_buckets(findings, narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert any(fn["entity"] == "appdb_prod" for fn in out["false_negations"])


@mock_aws
def test_grounding_passes_on_correct_no_findings_statement():
    narrative = {
        "executive_summary": "No findings this cycle.",
        "theme_clusters": [],
        "finding_narratives": [],
    }
    _setup_buckets([], narrative)
    out = lambda_handler(_event(), None)
    assert out["passed"] is True
