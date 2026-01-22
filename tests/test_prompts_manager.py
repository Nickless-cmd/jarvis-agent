import hashlib
from pathlib import Path

from jarvis.prompt_manager import PromptManager, get_prompt_manager


def test_prompt_manager_defaults():
    pm = get_prompt_manager()
    bundle = pm.effective_prompt(is_admin=False)
    assert bundle.text
    assert bundle.sha256 == hashlib.sha256(bundle.text.encode("utf-8")).hexdigest()


def test_prompt_manager_admin_overlay(tmp_path: Path):
    user_text = "USER PROMPT"
    admin_text = "ADMIN PROMPT"
    (tmp_path / "system_user.txt").write_text(user_text, encoding="utf-8")
    (tmp_path / "system_admin.txt").write_text(admin_text, encoding="utf-8")
    pm = PromptManager(prompts_dir=tmp_path)
    assert pm.effective_prompt(is_admin=False).text == user_text
    assert pm.effective_prompt(is_admin=True).text == admin_text


def test_prompt_preview_and_hash(tmp_path: Path):
    text = "x" * 300
    (tmp_path / "system_user.txt").write_text(text, encoding="utf-8")
    pm = PromptManager(prompts_dir=tmp_path)
    bundle = pm.effective_prompt(is_admin=False)
    assert bundle.preview(50).endswith("…")
    assert bundle.sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_prompt_endpoint():
    """Test the /v1/prompt/active endpoint returns correct info."""
    from fastapi.testclient import TestClient
    from jarvis import server
    from jarvis.auth import register_user, login_user
    
    # Register and login to get token
    try:
        register_user("testuser", "secret", email="test@example.com")
    except Exception:
        pass
    
    login = login_user("testuser", "secret")
    token = login["token"]
    
    client = TestClient(server.app)
    # Use x_user_token header for user authentication
    resp = client.get("/v1/prompt/active", headers={"x-user-token": token})
    assert resp.status_code == 200
    
    data = resp.json()
    assert "prompt" in data
    assert "is_admin" in data
    assert "build_id" in data
    
    prompt_info = data["prompt"]
    assert "name" in prompt_info
    assert "hash" in prompt_info
    # Preview only shown for admin or when _EXPOSE_SYSTEM_PROMPT is True
    if data["is_admin"] or server._EXPOSE_SYSTEM_PROMPT:
        assert "preview" in prompt_info
    else:
        assert "preview" not in prompt_info
