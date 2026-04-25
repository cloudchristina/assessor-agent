import json
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws
from src.shared.models import JudgeScore


def _faithful_score() -> JudgeScore:
    return JudgeScore(
        faithfulness=0.95,
        completeness=0.97,
        fabrication=0.02,
        reasoning="All claims cite findings.",
        model_id="claude-haiku-4-5",
    )


def _fabricated_score() -> JudgeScore:
    return JudgeScore(
        faithfulness=0.4,
        completeness=0.5,
        fabrication=0.7,
        reasoning="Narrative invents principals.",
        model_id="claude-haiku-4-5",
    )


def _setup_s3() -> None:
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    s3.put_object(
        Bucket="test-bucket-123",
        Key="findings.json",
        Body=json.dumps({"findings": [{"finding_id": "F-1"}]}).encode(),
    )
    s3.put_object(
        Bucket="test-bucket-123",
        Key="narrative.json",
        Body=json.dumps({"total_findings": 1, "executive_summary": "ok"}).encode(),
    )


def _event():
    return {
        "findings_s3_uri": "s3://test-bucket-123/findings.json",
        "narrative_s3_uri": "s3://test-bucket-123/narrative.json",
    }


def _agent_result(score: JudgeScore) -> MagicMock:
    """Mimic strands.AgentResult — only the attribute we use."""
    res = MagicMock()
    res.structured_output = score
    return res


@mock_aws
def test_faithful_narrative_passes():
    _setup_s3()
    fake_agent = MagicMock(return_value=_agent_result(_faithful_score()))
    with patch("src.judge.handler._build_agent", return_value=fake_agent):
        from src.judge.handler import lambda_handler
        out = lambda_handler(_event(), None)
    fake_agent.assert_called_once()
    assert fake_agent.call_args.kwargs.get("structured_output_model") is JudgeScore
    assert out["passed"] is True
    assert out["passed_int"] == 1
    assert out["faithfulness"] >= 0.9


@mock_aws
def test_fabricated_narrative_fails():
    _setup_s3()
    fake_agent = MagicMock(return_value=_agent_result(_fabricated_score()))
    with patch("src.judge.handler._build_agent", return_value=fake_agent):
        from src.judge.handler import lambda_handler
        out = lambda_handler(_event(), None)
    assert out["passed"] is False
    assert out["passed_int"] == 0
    assert out["fabrication"] > 0.05
