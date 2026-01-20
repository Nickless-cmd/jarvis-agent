"""
Agent orchestrator - coordinates agent execution.
"""

def handle_turn(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle a single turn of agent interaction.
    Calls the internal agent implementation.
    """
    from jarvis.agent import _run_agent_impl
    return _run_agent_impl(
        user_id=user_id,
        prompt=prompt,
        session_id=session_id,
        allowed_tools=allowed_tools,
        ui_city=ui_city,
        ui_lang=ui_lang,
    )