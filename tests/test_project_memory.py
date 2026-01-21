from jarvis.agent_core import project_memory as pm


def test_add_and_summarize(tmp_path):
    path = tmp_path / "pm.json"
    assert pm.add_decision("Use English comments", path=str(path))
    assert pm.add_milestone("Refactored agent orchestrator", path=str(path))
    assert pm.add_roadmap_item("Split remaining skills", path=str(path))
    bullets = pm.summarize_project_state(path=str(path))
    assert any("Decision" in b for b in bullets)
    assert any("Done" in b for b in bullets)
    assert any("Upcoming" in b for b in bullets)


def test_redaction_blocks_secrets(tmp_path):
    path = tmp_path / "pm.json"
    assert pm.add_decision("contains token abc", path=str(path)) is False
    data = pm._load(path=str(path))
    assert data["decisions"] == []
