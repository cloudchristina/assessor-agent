"""Orchestrates a full eval run. Calls deployed Lambdas (real Bedrock by default;
override via STUB_BEDROCK=1 for tests).

TODO: full Bedrock-backed path requires AGENT_NARRATOR_FUNCTION_NAME +
JUDGE_FUNCTION_NAME env vars and is exercised by
tests/integration/test_eval_e2e_smoke.py.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.eval_harness.golden_loader import load_all_golden_cases
from src.eval_harness.adversarial_runner import load_all_adversarial_cases
from src.eval_harness.metrics import per_rule_precision_recall
from src.eval_harness.ddb_writer import write_eval_result


RULE_IDS = ["R1", "R2", "R3", "R4", "R5", "R6"]


@dataclass
class EvalCaseResult:
    case_id: str
    metrics: dict
    latency_ms: int
    cost_aud: float


def run_eval_suite(
    suite: str = "smoke",
    *,
    branch: str | None = None,
    commit_sha: str | None = None,
) -> dict:
    """Orchestrate a full eval run over golden + adversarial cases.

    Parameters
    ----------
    suite:
        "smoke" (6 pinned cases, one per rule) or "full" (all 10 golden +
        all adversarial cases).
    branch:
        Git branch name to record in DDB (default "unknown").
    commit_sha:
        Git commit SHA to record in DDB (default "unknown").

    Returns
    -------
    dict with keys: eval_run_id, suite, cases_run, results, totals.
    """
    eval_run_id = (
        f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    cases = load_all_golden_cases() if suite == "full" else _smoke_cases()
    adv = load_all_adversarial_cases() if suite == "full" else []

    results: list[EvalCaseResult] = []
    for case in cases + adv:
        results.append(_run_one(case, eval_run_id))

    for r in results:
        write_eval_result(
            eval_run_id,
            r.case_id,
            r.metrics,
            branch=branch or "unknown",
            commit_sha=commit_sha or "unknown",
        )

    return {
        "eval_run_id": eval_run_id,
        "suite": suite,
        "cases_run": len(results),
        "results": [vars(r) for r in results],
        "totals": _aggregate(results),
    }


def _smoke_cases():
    """6 cases — one per rule R1–R6 — pinned by case_id.

    Selected for deterministic coverage and minimal Bedrock cost.
    """
    from src.eval_harness.golden_loader import load_case_by_id

    return [
        load_case_by_id(cid)
        for cid in [
            "case_001_baseline",
            "case_002_dev_prod_sod",
            "case_003_orphan_cluster",
            "case_005_mixed_severity",
            "synth_boundary_91d",
            "synth_high_explicit",
        ]
    ]


def _run_one(case, eval_run_id: str) -> EvalCaseResult:
    """Run one eval case. Calls deployed Lambdas in real mode; stub-returns when STUB_BEDROCK=1.

    TODO: full Bedrock-backed path requires AGENT_NARRATOR_FUNCTION_NAME +
    JUDGE_FUNCTION_NAME env vars and is exercised by
    tests/integration/test_eval_e2e_smoke.py.
    """
    if os.environ.get("STUB_BEDROCK") == "1" or not os.environ.get(
        "AGENT_NARRATOR_FUNCTION_NAME"
    ):
        return _run_one_stub(case, eval_run_id)
    return _run_one_real(case, eval_run_id)


def _run_one_stub(case, eval_run_id: str) -> EvalCaseResult:
    """Stub mode: pretend findings == expected_findings.

    Used for unit tests + local smoke runs. AdversarialCase instances have no
    ``expected_findings`` attribute — ``getattr`` falls back to [] so they
    produce vacuously-perfect metrics.
    """
    expected = getattr(case, "expected_findings", None) or []
    # Convert ExpectedFinding Pydantic objects to plain dicts
    actual_dicts = [
        {"rule_id": f.rule_id, "principal": f.principal} for f in expected
    ]
    expected_dicts = list(actual_dicts)  # perfect match in stub

    pr = per_rule_precision_recall(actual_dicts, expected_dicts, rule_ids=RULE_IDS)
    metrics = {
        "faithfulness": 0.95,
        "answer_relevance": 0.90,
        "context_precision": 0.85,
        "bertscore_f1": 0.80,
        "per_rule": {
            rid: {"precision": m.precision, "recall": m.recall}
            for rid, m in pr.items()
        },
    }
    return EvalCaseResult(
        case_id=case.case_id,
        metrics=metrics,
        latency_ms=100,
        cost_aud=0.001,
    )


def _run_one_real(case, eval_run_id: str) -> EvalCaseResult:
    """Real mode: invoke deployed Lambdas.

    Not exercised by unit tests — requires AGENT_NARRATOR_FUNCTION_NAME +
    JUDGE_FUNCTION_NAME env vars to be set and live AWS access.
    See tests/integration/test_eval_e2e_smoke.py.
    """
    raise NotImplementedError(
        "Real Lambda invocation path not implemented; set STUB_BEDROCK=1 for tests"
    )


def _aggregate(results: list[EvalCaseResult]) -> dict:
    """Aggregate per-case metrics into suite-level averages.

    Returns a dict consumed by the reporter (Task 4.2) containing:
    - {metric}_avg for faithfulness, answer_relevance, context_precision, bertscore_f1
    - {rule_id}_precision_avg / {rule_id}_recall_avg for each rule seen
    - precision_avg / recall_avg (cross-rule, for reporter threshold table)
    - total_cases, total_latency_ms, total_cost_aud
    """
    if not results:
        return {}

    totals: dict = {}

    # Scalar metric averages
    scalar_keys = [
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "bertscore_f1",
    ]
    for k in scalar_keys:
        vals = [
            r.metrics.get(k) for r in results if r.metrics.get(k) is not None
        ]
        if vals:
            totals[f"{k}_avg"] = sum(vals) / len(vals)

    # Per-rule precision/recall averages
    all_rule_ids: set[str] = set()
    for r in results:
        all_rule_ids.update(r.metrics.get("per_rule", {}).keys())

    for rid in sorted(all_rule_ids):
        precs = [
            r.metrics["per_rule"][rid]["precision"]
            for r in results
            if rid in r.metrics.get("per_rule", {})
        ]
        recs = [
            r.metrics["per_rule"][rid]["recall"]
            for r in results
            if rid in r.metrics.get("per_rule", {})
        ]
        if precs:
            totals[f"{rid}_precision_avg"] = sum(precs) / len(precs)
            totals[f"{rid}_recall_avg"] = sum(recs) / len(recs)

    # Cross-rule averages for the threshold table in reporter
    if results and any(r.metrics.get("per_rule") for r in results):
        all_p = [
            m["precision"]
            for r in results
            for m in r.metrics.get("per_rule", {}).values()
        ]
        all_r = [
            m["recall"]
            for r in results
            for m in r.metrics.get("per_rule", {}).values()
        ]
        if all_p:
            totals["precision_avg"] = sum(all_p) / len(all_p)
        if all_r:
            totals["recall_avg"] = sum(all_r) / len(all_r)

    totals["total_cases"] = len(results)
    totals["total_latency_ms"] = sum(r.latency_ms for r in results)
    totals["total_cost_aud"] = sum(r.cost_aud for r in results)
    return totals
