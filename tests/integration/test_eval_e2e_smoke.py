"""End-to-end smoke test for the eval suite. Runs ``make eval-smoke`` against the
deployed dev environment, then verifies the eval_results DDB table.

Required env vars
-----------------
RUN_INTEGRATION_TESTS=1          opt-in guard
AWS_PROFILE                      e.g. sso-cc1-devops
AWS_REGION                       default ap-southeast-2
EVAL_RESULTS_TABLE               DynamoDB table name for eval results
STATE_MACHINE_ARN                Step Functions ARN (informational; used by eval_run CLI)
RUNS_TABLE                       DynamoDB table holding pipeline run records

Skipped by default. To run::

    RUN_INTEGRATION_TESTS=1 AWS_PROFILE=sso-cc1-devops \\
        .venv/bin/python -m pytest tests/integration/test_eval_e2e_smoke.py -v -s
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import boto3
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration test requires sandbox AWS creds; set RUN_INTEGRATION_TESTS=1 to run",
)


def test_eval_smoke_runs_six_cases_and_persists(tmp_path: pytest.TempPathFactory) -> None:
    """Run the eval CLI against the smoke suite and verify DDB persistence."""
    out_json = tmp_path / "eval_run.json"

    # Run the CLI in stub mode (real Bedrock-backed _run_one_real not yet
    # implemented; runner falls back to deterministic per-case metrics).
    # The integration value here is the DDB persistence path against the
    # deployed eval_results table — the metric computation is exercised by
    # the unit suite.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.eval_run",
            "--suite=smoke",
            f"--out={out_json}",
        ],
        env={
            **os.environ,
            "STUB_BEDROCK": "1",
            "AWS_DEFAULT_REGION": os.environ.get("AWS_REGION", "ap-southeast-2"),
        },
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"eval_run exited {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    result = json.loads(out_json.read_text())
    assert result["cases_run"] == 6, f"expected 6 cases, got {result['cases_run']}"
    assert result["suite"] == "smoke"
    assert "totals" in result and result["totals"]
    eval_run_id = result["eval_run_id"]

    # Verify DDB persistence — one row per case
    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-southeast-2"))
    table = ddb.Table(os.environ["EVAL_RESULTS_TABLE"])
    resp = table.query(
        KeyConditionExpression="eval_run_id = :r",
        ExpressionAttributeValues={":r": eval_run_id},
    )
    assert len(resp["Items"]) == 6, f"expected 6 rows in DDB, got {len(resp['Items'])}"
