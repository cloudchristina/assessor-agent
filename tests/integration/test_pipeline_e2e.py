"""End-to-end pipeline tests against a deployed sandbox.

These tests SKIP when the sandbox env vars are missing. To run them:

    STATE_MACHINE_ARN=...        \\
    SANDBOX_RUNS_BUCKET=...      \\
    SANDBOX_RUNS_TABLE=...       \\
    SANDBOX_FINDINGS_TABLE=...   \\
    pytest tests/integration/test_pipeline_e2e.py -v
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest


REQUIRED_ENV = ("STATE_MACHINE_ARN", "SANDBOX_RUNS_BUCKET", "SANDBOX_RUNS_TABLE", "SANDBOX_FINDINGS_TABLE")
POLL_TIMEOUT_SECS = 300
POLL_INTERVAL_SECS = 5


def _have_sandbox() -> bool:
    return all(os.environ.get(k) for k in REQUIRED_ENV)


pytestmark = pytest.mark.skipif(
    not _have_sandbox(),
    reason=f"sandbox env vars not set: need {', '.join(REQUIRED_ENV)}",
)


@pytest.fixture
def sandbox():
    import boto3

    region = os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-2")
    return {
        "region": region,
        "runs_bucket": os.environ["SANDBOX_RUNS_BUCKET"],
        "runs_table": os.environ["SANDBOX_RUNS_TABLE"],
        "findings_table": os.environ["SANDBOX_FINDINGS_TABLE"],
        "state_machine_arn": os.environ["STATE_MACHINE_ARN"],
        "s3": boto3.client("s3", region_name=region),
        "ddb": boto3.resource("dynamodb", region_name=region),
        "sfn": boto3.client("stepfunctions", region_name=region),
    }


def _upload_fixture(sandbox, fixture_path: Path) -> str:
    """Upload the fixture CSV to S3 at the synthetic-data location and return
    the s3:// URI. The extractor's SYNTHETIC_DATA_S3_URI env var must point
    at this key on the sandbox Lambda configuration (set as a one-time
    sandbox override; out of scope for this test to configure)."""
    key = f"fixtures/synth-{datetime.now().timestamp()}.csv"
    sandbox["s3"].put_object(
        Bucket=sandbox["runs_bucket"],
        Key=key,
        Body=fixture_path.read_bytes(),
    )
    return f"s3://{sandbox['runs_bucket']}/{key}"


def _trigger_run(sandbox, cadence: str) -> str:
    """Start an SFN execution and return the run_id the extractor will mint."""
    now_sydney = datetime.now(ZoneInfo("Australia/Sydney"))
    started_at = now_sydney.isoformat()
    exec_resp = sandbox["sfn"].start_execution(
        stateMachineArn=sandbox["state_machine_arn"],
        input=json.dumps({"cadence": cadence, "started_at": started_at}),
    )
    return exec_resp["executionArn"]


def _wait_for_terminal(sandbox, execution_arn: str, timeout: int = POLL_TIMEOUT_SECS) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        desc = sandbox["sfn"].describe_execution(executionArn=execution_arn)
        if desc["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            return desc
        time.sleep(POLL_INTERVAL_SECS)
    raise TimeoutError(f"execution {execution_arn} did not reach terminal state within {timeout}s")


def _get_run(sandbox, run_id: str) -> dict:
    return sandbox["ddb"].Table(sandbox["runs_table"]).get_item(Key={"run_id": run_id})["Item"]


def _list_findings(sandbox, run_id: str) -> list[dict]:
    resp = sandbox["ddb"].Table(sandbox["findings_table"]).query(
        KeyConditionExpression="run_id = :r",
        ExpressionAttributeValues={":r": run_id},
    )
    return resp.get("Items", [])


def test_weekly_run_completes_and_produces_findings(sandbox):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_uar_minimal.csv"
    _upload_fixture(sandbox, fixture)

    exec_arn = _trigger_run(sandbox, cadence="weekly")
    desc = _wait_for_terminal(sandbox, exec_arn)
    assert desc["status"] == "SUCCEEDED"

    output = json.loads(desc["output"])
    run_id = output["validated"]["run_id"]

    run = _get_run(sandbox, run_id)
    assert run["status"] == "succeeded"
    assert run["findings_count"] > 0

    findings = _list_findings(sandbox, run_id)
    rule_ids = {f["rule_id"] for f in findings}
    assert "R1" in rule_ids
    assert "R6" in rule_ids

    narrative = sandbox["s3"].get_object(
        Bucket=sandbox["runs_bucket"],
        Key=f"narratives/{run_id}/narrative.json",
    )
    parsed = json.loads(narrative["Body"].read())
    assert "executive_summary" in parsed
    assert parsed["total_findings"] == run["findings_count"]


def test_monthly_run_also_produces_pdf(sandbox):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_uar_minimal.csv"
    _upload_fixture(sandbox, fixture)

    exec_arn = _trigger_run(sandbox, cadence="monthly")
    desc = _wait_for_terminal(sandbox, exec_arn)
    assert desc["status"] == "SUCCEEDED"

    output = json.loads(desc["output"])
    run_id = output["validated"]["run_id"]
    pdf_uri = output.get("pdf", {}).get("pdf_s3_uri")
    assert pdf_uri is not None and pdf_uri.endswith(".pdf")


def test_prompt_injection_is_caught_by_gates(sandbox):
    """The demo centrepiece: a CSV row whose login_name tries to jailbreak
    the narrator is either flagged as a finding (rules engine still sees it)
    or the narrative is rejected by the citation / entity-grounding gate."""
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "prompt_injection_row.csv"
    _upload_fixture(sandbox, fixture)

    exec_arn = _trigger_run(sandbox, cadence="weekly")
    desc = _wait_for_terminal(sandbox, exec_arn)

    # Pipeline should complete one way or the other (succeeded-with-quarantine is fine)
    output = json.loads(desc["output"])
    run_id = output.get("validated", {}).get("run_id") or output.get("extract", {}).get("run_id")
    assert run_id, f"no run_id in execution output: {output}"

    run = _get_run(sandbox, run_id)
    assert run["status"] in ("succeeded", "quarantined", "failed")

    findings = _list_findings(sandbox, run_id)
    # The injection row's login_name should appear either as an R1 or R6 finding.
    injection_hit = any("admin_backup" in f.get("principal", "") for f in findings)
    assert injection_hit, "rules engine should still flag the injected row even if narrator was bypassed"

    # Either the narrative cited cleanly (gates pass) or grounding caught fabrication
    gates = run.get("gates", {})
    assert gates.get("citation") is True or gates.get("entity_grounding") is False
