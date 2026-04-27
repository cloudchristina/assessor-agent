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


def _fake_agent_result() -> MagicMock:
    """Mimic strands.AgentResult — only the attribute we use."""
    res = MagicMock()
    res.structured_output = _fake_report()
    return res


@mock_aws
def test_handler_writes_narrative_to_s3():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    findings_doc = {"findings": [{
        "finding_id": "F-1", "rule_id": "R1", "severity": "CRITICAL",
        "principal": "alice", "databases": ["appdb"],
        "ism_controls": ["ISM-1546"], "evidence": {},
    }]}
    s3.put_object(
        Bucket="test-bucket-123",
        Key="rules/run_x/findings.json",
        Body=json.dumps(findings_doc).encode("utf-8"),
    )

    # Modern Strands API: agent(prompt, structured_output_model=Model) returns
    # AgentResult with .structured_output populated. Tool-use loop runs in __call__.
    fake_agent = MagicMock(return_value=_fake_agent_result())

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

    # Critical: handler MUST call agent(...) with structured_output_model, not
    # the deprecated agent.structured_output(...) method.
    # With CRITICAL findings in the summary the self-consistency check fires,
    # so the agent is called 3× total (1 primary + 2 extra at temperature=0.3).
    assert fake_agent.call_count == 3, (
        f"Expected 3 agent calls (1 primary + 2 self-consistency), got {fake_agent.call_count}"
    )
    # All calls must use the modern structured-output API.
    for call in fake_agent.call_args_list:
        assert call.kwargs.get("structured_output_model") is NarrativeReport, (
            "handler must use modern Strands API: agent(prompt, structured_output_model=...)"
        )

    body = s3.get_object(Bucket="test-bucket-123", Key="narratives/run_x/narrative.json")["Body"].read()
    data = json.loads(body)
    assert data["total_findings"] == 1
    assert data["executive_summary"].startswith("One critical")


def test_build_agent_registers_all_four_tools():
    """Tools must be wired into the Agent so the model can invoke them."""
    from src.agent_narrator import handler as h
    from src.agent_narrator.tools import (
        get_finding, get_ism_control, get_rule_spec, get_prior_cycle_summary,
    )
    expected_tools = {get_finding, get_ism_control, get_rule_spec, get_prior_cycle_summary}

    # Patch Agent constructor to capture what tools are passed
    captured: dict = {}

    class _AgentSpy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch("src.agent_narrator.handler.Agent", _AgentSpy), \
         patch("src.agent_narrator.handler.BedrockModel", MagicMock()):
        h._build_agent()

    tools_passed = set(captured.get("tools") or [])
    assert tools_passed == expected_tools, (
        f"Agent must be built with all four tools registered. "
        f"Got: {tools_passed}, expected: {expected_tools}"
    )
