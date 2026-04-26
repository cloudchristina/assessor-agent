"""Tests for adversarial case loading."""
from src.eval_harness.adversarial_runner import load_all_adversarial_cases


def test_load_all_six_adversarial_cases():
    cases = load_all_adversarial_cases()
    assert len(cases) == 6
    expected_ids = {
        "prompt_injection_row", "empty_findings", "10k_findings",
        "boundary_89d_vs_90d", "duplicate_sid", "evidence_injection",
    }
    assert {c.case_id for c in cases} == expected_ids
