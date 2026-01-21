from jarvis.agent_skills import recap_skill as rs


def test_recap_intent_detection():
    is_recap, chat_id, snap_id = rs._recap_intent("Analysér chatlog 12 og snapshot 3")
    assert is_recap
    assert chat_id == 12
    assert snap_id == 3


def test_analyze_text_parses_sections():
    text = """
    Done: extracted files_skill
    TODO: wire recap skill
    tests not green on process flow
    """
    result = rs._analyze_text(text)
    assert any("extracted" in c for c in result["completed"])
    assert any("wire recap" in p for p in result["pending"])
    assert any("tests not green" in r for r in result["risks"])


def test_format_report():
    report = rs._format_report(
        ["Done A"], ["Next B"], ["Risk C"], ui_lang="da"
    )
    assert "Færdigt" in report or "Completed" in report
