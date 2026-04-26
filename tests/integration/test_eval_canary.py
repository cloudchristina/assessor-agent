"""End-to-end canary + reviewer-disagreement flow.

Required env vars
-----------------
RUN_INTEGRATION_TESTS=1              opt-in guard
AWS_PROFILE                          e.g. sso-cc1-devops
AWS_REGION                           default ap-southeast-2
CANARY_ORCHESTRATOR_FUNCTION_NAME    Lambda function name for the canary orchestrator
CANARY_RESULTS_TABLE                 DynamoDB table for canary results
FINDINGS_TABLE                       DynamoDB table holding pipeline findings
GOLDEN_SET_CANDIDATES_TABLE          DynamoDB table for golden-set candidates

Skipped by default. To run::

    RUN_INTEGRATION_TESTS=1 AWS_PROFILE=sso-cc1-devops \\
        .venv/bin/python -m pytest tests/integration/test_eval_canary.py -v -s
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import boto3
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration test requires sandbox AWS creds; set RUN_INTEGRATION_TESTS=1 to run",
)

_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")


def test_canary_orchestrator_writes_three_results() -> None:
    """Manually invoke the canary_orchestrator Lambda; assert 3 canary_results rows appear."""
    lam = boto3.client("lambda", region_name=_REGION)
    ddb = boto3.resource("dynamodb", region_name=_REGION)
    canary_table = ddb.Table(os.environ["CANARY_RESULTS_TABLE"])

    # Snapshot current row count
    before = canary_table.scan(Select="COUNT")["Count"]

    # Trigger canary orchestrator
    resp = lam.invoke(
        FunctionName=os.environ["CANARY_ORCHESTRATOR_FUNCTION_NAME"],
        InvocationType="RequestResponse",
        Payload=json.dumps({}),
    )
    payload = json.loads(resp["Payload"].read())
    assert resp["StatusCode"] == 200, f"invoke failed: {payload}"

    # Allow time for async writes — canary processes 3 fixtures sequentially via SFN
    deadline = time.time() + 600  # 10 minutes
    after = before
    while time.time() < deadline and after < before + 3:
        time.sleep(15)
        after = canary_table.scan(Select="COUNT")["Count"]
    assert after >= before + 3, (
        f"expected 3 new canary_results rows; got {after - before}"
    )


def test_simulate_disagreement_writes_candidate() -> None:
    """Pick a CRITICAL finding; simulate a reviewer disagreement; assert candidate row appears."""
    ddb = boto3.resource("dynamodb", region_name=_REGION)
    findings_table = ddb.Table(os.environ["FINDINGS_TABLE"])
    candidates_table = ddb.Table(os.environ["GOLDEN_SET_CANDIDATES_TABLE"])

    # Find a CRITICAL finding to flip to false_positive (triggers disagreement)
    resp = findings_table.scan(
        FilterExpression="severity = :s",
        ExpressionAttributeValues={":s": "CRITICAL"},
        Limit=1,
    )
    assert resp["Items"], "no CRITICAL findings to test against"
    finding = resp["Items"][0]
    finding_id = finding["finding_id"]
    run_id = finding["run_id"]

    # Snapshot candidate count
    before = candidates_table.scan(Select="COUNT")["Count"]

    # Run the disagreement simulator
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.simulate_disagreement",
            f"--run-id={run_id}",
            f"--finding-id={finding_id}",
            "--decision=false_positive",
            "--rationale=integration-test simulated disagreement",
        ],
        check=True,
        env={**os.environ, "FINDINGS_TABLE": os.environ["FINDINGS_TABLE"]},
    )

    # reviewer_disagreement Lambda processes the DDB stream event asynchronously
    deadline = time.time() + 60
    after = before
    while time.time() < deadline and after <= before:
        time.sleep(5)
        after = candidates_table.scan(Select="COUNT")["Count"]
    assert after > before, (
        f"expected new candidate row; before={before} after={after}"
    )
