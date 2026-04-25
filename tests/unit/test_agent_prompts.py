from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_bans_invented_ids():
    assert "NEVER invent finding IDs" in SYSTEM_PROMPT
    assert "Every claim" in SYSTEM_PROMPT
    for name in ("get_finding", "get_ism_control", "get_rule_spec", "get_prior_cycle_summary"):
        assert name in SYSTEM_PROMPT


def test_user_prompt_lists_ids_and_summary_without_uar_data():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={"R1": 1, "CRITICAL": 1},
        finding_ids=["F-1", "F-2"],
        prior_run_id=None,
    )
    assert "Run ID: run_x" in prompt
    assert "F-1" in prompt
    assert "F-2" in prompt
    # Sanity: no raw-row keywords ever make it into the user prompt
    for leaky in ("login_name", "mapped_user_name", "LoginSid", "password"):
        assert leaky not in prompt


def test_user_prompt_includes_prior_cycle_when_given():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={},
        finding_ids=[],
        prior_run_id="run_prev",
    )
    assert "Prior cycle: run_prev" in prompt
