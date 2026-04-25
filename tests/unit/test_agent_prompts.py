from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_bans_invented_ids():
    assert "NEVER invent finding IDs" in SYSTEM_PROMPT
    assert "Every claim" in SYSTEM_PROMPT
    # Final action must be a tool call so structured_output succeeds.
    assert "tool call with the NarrativeReport schema" in SYSTEM_PROMPT


def test_user_prompt_lists_ids_and_summary():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={"R1": 1, "CRITICAL": 1},
        finding_ids=["F-1", "F-2"],
        prior_run_id=None,
    )
    assert "RUN_ID: run_x" in prompt
    assert "F-1" in prompt
    assert "F-2" in prompt
    # Without explicit findings/controls/rules args, the prompt should NOT
    # leak any UAR-shaped fields.
    for leaky in ("login_name", "mapped_user_name", "LoginSid", "password"):
        assert leaky not in prompt


def test_user_prompt_includes_prior_cycle_when_given():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={},
        finding_ids=[],
        prior_run_id="run_prev",
    )
    assert "PRIOR_RUN_ID: run_prev" in prompt


def test_user_prompt_inlines_findings_when_provided():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={"R1": 1},
        finding_ids=["F-1"],
        prior_run_id=None,
        findings=[{"finding_id": "F-1", "principal": "alice", "rule_id": "R1"}],
        ism_controls=[{"control_id": "ISM-1546", "title": "MFA", "intent": "..."}],
        rules=[{"rule_id": "R1", "severity": "CRITICAL", "description": "..."}],
    )
    assert "FINDINGS:" in prompt
    assert "ISM_CONTROLS:" in prompt
    assert "RULES:" in prompt
    assert "ISM-1546" in prompt
