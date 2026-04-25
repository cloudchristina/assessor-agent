import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws
from src.shared.models import NarrativeReport


def _fake_report() -> NarrativeReport:
    return NarrativeReport(
        run_id="run_x",
        executive_summary="One critical finding.",
        theme_clusters=[],
        finding_narratives=[],
        cycle_over_cycle=None,
        total_findings=1,
        model_id="claude-sonnet-4-6",
        generated_at=datetime(2026, 4, 25, 9, 0, 0),
    )


@mock_aws
def test_handler_writes_narrative_to_s3():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    fake_agent = MagicMock()
    fake_agent.structured_output.return_value = _fake_report()
    fake_agent.input_tokens = 100
    fake_agent.output_tokens = 50

    with patch("src.agent_narrator.handler._build_agent", return_value=fake_agent):
        from src.agent_narrator.handler import lambda_handler
        result = lambda_handler({
            "run_id": "run_x",
            "bucket": "test-bucket-123",
            "summary": {"R1": 1, "CRITICAL": 1},
            "finding_ids": ["F-1"],
        }, None)

    assert result["run_id"] == "run_x"
    assert result["model_id"] == "claude-sonnet-4-6"
    assert result["narrative_s3_uri"] == "s3://test-bucket-123/narratives/run_x/narrative.json"

    body = s3.get_object(Bucket="test-bucket-123", Key="narratives/run_x/narrative.json")["Body"].read()
    data = json.loads(body)
    assert data["total_findings"] == 1
    assert data["executive_summary"].startswith("One critical")
