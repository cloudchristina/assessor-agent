import pytest
from src.shared.models import ExpectedFinding, GoldenCase
from src.eval_harness.golden_loader import load_all_golden_cases, load_case_by_id


def test_golden_case_minimal():
    case = GoldenCase(
        case_id="case_001_baseline",
        input_csv="evals/golden/fixtures/case_001.csv",
        expected_findings=[
            ExpectedFinding(rule_id="R1", principal="svc_app", severity="CRITICAL"),
        ],
        expected_counts={"R1": 1, "R2": 0, "R3": 0, "R4": 0, "R5": 0, "R6": 0},
        must_mention=["svc_app", "ISM-1546"],
        must_not_mention=[],
    )
    assert case.case_id == "case_001_baseline"
    assert case.expected_findings[0].severity == "CRITICAL"


def test_load_all_finds_ten_cases():
    cases = load_all_golden_cases()
    assert len(cases) == 10
    ids = {c.case_id for c in cases}
    assert "case_001_baseline" in ids
    assert "synth_500_principals" in ids


def test_load_case_by_id_returns_correct_case():
    case = load_case_by_id("case_001_baseline")
    assert case.expected_counts["R1"] == 1


def test_load_case_by_id_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_case_by_id("nope")
