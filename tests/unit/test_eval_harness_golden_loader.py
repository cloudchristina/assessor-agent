from src.shared.models import ExpectedFinding, GoldenCase


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
