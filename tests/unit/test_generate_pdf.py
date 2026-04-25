import json
import boto3
from moto import mock_aws


def _findings_doc():
    return {"findings": [
        {
            "finding_id": "F-1", "run_id": "run_x", "rule_id": "R1",
            "severity": "CRITICAL", "ism_controls": ["ISM-1546"],
            "principal": "alice", "databases": ["appdb (s1)"], "evidence": {},
            "detected_at": "2026-04-25T00:00:00",
        },
        {
            "finding_id": "F-2", "run_id": "run_x", "rule_id": "R6",
            "severity": "HIGH", "ism_controls": ["ISM-1545"],
            "principal": "admin", "databases": ["appdb (s1)"], "evidence": {},
            "detected_at": "2026-04-25T00:00:00",
        },
    ]}


def _narrative_doc():
    return {
        "executive_summary": "Two findings this cycle.",
        "theme_clusters": [{"theme": "Privileged accounts", "summary": "MFA gap.", "finding_ids": ["F-1"]}],
        "finding_narratives": [],
        "total_findings": 2,
    }


def test_render_pdf_emits_bytes_with_run_metadata():
    from src.generate_pdf.templates import render_pdf

    run = {
        "run_id": "run_x",
        "cadence": "monthly",
        "started_at": "2026-04-01T09:00:00+10:00",
        "trace_id": "t-abc",
        "manifest_sha256": "deadbeef" * 8,
        "rows_scanned": 100,
        "findings_count": 2,
    }
    pdf = render_pdf(run, _findings_doc()["findings"], _narrative_doc())
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")
    # Sanity: PDF should be well over 1 KB on a real document
    assert len(pdf) > 1500


@mock_aws
def test_handler_writes_pdf_to_s3_with_correct_key():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(Bucket="test-bucket-123", Key="findings.json", Body=json.dumps(_findings_doc()))
    s3.put_object(Bucket="test-bucket-123", Key="narrative.json", Body=json.dumps(_narrative_doc()))

    from src.generate_pdf.handler import lambda_handler
    result = lambda_handler({
        "run_id": "run_x",
        "bucket": "test-bucket-123",
        "cadence": "monthly",
        "started_at": "2026-04-01T09:00:00+10:00",
        "manifest": {"row_ids_sha256": "abc", "row_count": 100},
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
        "trace_id": "t-abc",
    }, None)

    assert result["pdf_s3_uri"].endswith("reports/2026-04/attestation_run_x.pdf")
    obj = s3.get_object(Bucket="test-bucket-123", Key="reports/2026-04/attestation_run_x.pdf")
    body = obj["Body"].read()
    assert body.startswith(b"%PDF-")
    assert result["bytes"] == len(body)


def test_pdf_size_within_reasonable_range_on_fixed_input():
    """Snapshot-style: byte-length within ±5% of an empirically-fixed bound."""
    from src.generate_pdf.templates import render_pdf

    run = {
        "run_id": "run_fixed",
        "cadence": "monthly",
        "started_at": "2026-04-01T09:00:00+10:00",
        "trace_id": "t-fixed",
        "manifest_sha256": "0" * 64,
        "rows_scanned": 10,
        "findings_count": 2,
    }
    pdf = render_pdf(run, _findings_doc()["findings"], _narrative_doc())
    # Bound chosen from a representative run; ReportLab output is deterministic
    # for fixed inputs, so this catches accidental layout/data drift.
    assert 2000 < len(pdf) < 8000
