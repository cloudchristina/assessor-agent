from src.agent_narrator.prompts import SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_bans_invented_ids():
    assert "NEVER invent finding IDs" in SYSTEM_PROMPT
    assert "Every claim" in SYSTEM_PROMPT


def test_system_prompt_instructs_tool_use():
    """Modern Strands: agent uses tools to enrich; no inline findings."""
    for tool_name in ("get_finding", "get_ism_control", "get_rule_spec", "get_prior_cycle_summary"):
        assert tool_name in SYSTEM_PROMPT, f"system prompt must reference {tool_name}"


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
    # The prompt must NOT contain finding details — those come via tool calls.
    for leaky in ("login_name", "mapped_user_name", "LoginSid", "password",
                  "FINDINGS:", "ISM_CONTROLS:", "RULES:"):
        assert leaky not in prompt


def test_user_prompt_includes_prior_cycle_when_given():
    prompt = build_user_prompt(
        run_id="run_x",
        summary={},
        finding_ids=[],
        prior_run_id="run_prev",
    )
    assert "PRIOR_RUN_ID: run_prev" in prompt


def test_user_prompt_signature_does_not_accept_inline_findings():
    """Spec Layer 1: agent must NEVER receive raw findings/controls/rules inline."""
    import inspect
    sig = inspect.signature(build_user_prompt)
    forbidden = {"findings", "ism_controls", "rules"}
    leaked = forbidden & set(sig.parameters)
    assert not leaked, f"build_user_prompt must not accept inline-context kwargs; got {leaked}"
