import pytest
from jarvis.agent import (
    _validate_vision_format,
    _violates_vision_policy,
    _should_translate_vision_response,
    _translate_to_danish_if_needed,
)


class TestValidateVisionFormat:
    def test_valid_danish_format(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        ok, err = _validate_vision_format(text, "da")
        assert ok is True
        assert err is None

    def test_valid_english_format(self):
        text = "Colors: blue\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        ok, err = _validate_vision_format(text, "en")
        assert ok is True
        assert err is None

    def test_too_few_lines(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: hus\nAntal: 1"
        ok, err = _validate_vision_format(text, "da")
        assert ok is False
        assert "Forventede 5 linjer" in err

    def test_too_many_lines(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: hus\nAntal: 1\nPlacering: midt\nEkstra: linje"
        ok, err = _validate_vision_format(text, "da")
        assert ok is False
        assert "Forventede 5 linjer" in err

    def test_wrong_label(self):
        text = "Farver: blå\nForm: rektangel\nObjekter: hus\nAntal: 1\nPlacering: midt"
        ok, err = _validate_vision_format(text, "da")
        assert ok is False
        assert "Forventede 'Former:'" in err

    def test_missing_value(self):
        text = "Farver:\nFormer: rektangel\nObjekter: hus\nAntal: 1\nPlacering: midt"
        ok, err = _validate_vision_format(text, "da")
        assert ok is False
        assert "Manglende værdi efter 'Farver:'" in err

    def test_leading_bullets_stripped(self):
        text = "- Farver: blå\n* Former: linjer\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        ok, err = _validate_vision_format(text, "da")
        assert ok is True
        assert err is None


class TestViolatesVisionPolicy:
    def test_no_violation_danish(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False

    def test_no_violation_english(self):
        text = "Colors: blue\nShapes: lines\nObjects: boat\nCount: 1\nPosition: center"
        violates, reason = _violates_vision_policy(text, "en")
        assert violates is False

    def test_place_name_violation(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: hus\nAntal: 1\nPlacering: Norge"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True

    def test_guess_word_violation(self):
        text = "Colors: blue\nShapes: looks like rectangle\nObjects: house\nCount: 1\nPosition: center"
        violates, reason = _violates_vision_policy(text, "en")
        assert violates is True

    def test_activity_violation(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: sejler på båd\nAntal: 1\nPlacering: midt"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True

    def test_uncertain_allowed(self):
        text = "Farver: usikkert\nFormer: usikkert\nObjekter: usikkert\nAntal: usikkert\nPlacering: usikkert"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False

    def test_uncertain_english_allowed(self):
        text = "Colors: uncertain\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        violates, reason = _violates_vision_policy(text, "en")
        assert violates is False

    def test_forbidden_word_case_insensitive(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: hus\nAntal: 1\nPlacering: DANMARK"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True

    def test_ultra_safe_valid_danish(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False

    def test_ultra_safe_forbidden_environment(self):
        text = "Farver: blå\nFormer: kurver\nObjekter: hav\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True
        assert "hav" in reason

    def test_ultra_safe_forbidden_guess(self):
        text = "Farver: blå\nFormer: rektangler\nObjekter: ligner båd\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True
        assert "ligner" in reason

    def test_ultra_safe_shapes_allowed(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False

    def test_ultra_safe_shapes_forbidden(self):
        text = "Farver: blå\nFormer: båd\nObjekter: båd\nAntal: 1\nPlacering: centrum"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True
        assert "båd" in reason

    def test_ultra_safe_position_allowed(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: venstre"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False

    def test_ultra_safe_position_forbidden(self):
        text = "Farver: blå\nFormer: linjer\nObjekter: båd\nAntal: 1\nPlacering: kyst"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is True
        assert "kyst" in reason

    def test_ultra_safe_uncertain_allowed(self):
        text = "Farver: usikkert\nFormer: usikkert\nObjekter: usikkert\nAntal: usikkert\nPlacering: usikkert"
        violates, reason = _violates_vision_policy(text, "da")
        assert violates is False


class TestShouldTranslateVisionResponse:
    def test_no_translate_danish_labels(self):
        text = "Farver: blå\nFormer: rektangel\nObjekter: hus\nAntal: 1\nPlacering: midt"
        assert _should_translate_vision_response(text, "da") is False

    def test_translate_english_labels_danish_lang(self):
        text = "Colors: blue\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        assert _should_translate_vision_response(text, "da") is True

    def test_no_translate_danish_content(self):
        text = "Farver: blå og grøn\nFormer: rektangel og cirkel\nObjekter: hus og båd\nAntal: 2\nPlacering: midt"
        assert _should_translate_vision_response(text, "da") is False

    def test_no_translate_english_lang(self):
        text = "Colors: blue\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        assert _should_translate_vision_response(text, "en") is False


class TestTranslateToDanishIfNeeded:
    def test_translate_failure_returns_original(self, monkeypatch):
        # Mock call_ollama to simulate failure
        def mock_call_ollama(*args, **kwargs):
            return {"error": "timeout"}
        monkeypatch.setattr("jarvis.agent.call_ollama", mock_call_ollama)

        text = "Colors: blue\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        result = _translate_to_danish_if_needed(text)
        assert result == text  # Should return original on failure

    def test_translate_empty_response_returns_original(self, monkeypatch):
        def mock_call_ollama(*args, **kwargs):
            return {"choices": [{"message": {"content": ""}}]}
        monkeypatch.setattr("jarvis.agent.call_ollama", mock_call_ollama)

        text = "Colors: blue\nShapes: rectangle\nObjects: house\nCount: 1\nPosition: center"
        result = _translate_to_danish_if_needed(text)
        assert result == text  # Should return original on empty translation

    def test_translate_success(self, monkeypatch):
        def mock_call_ollama(*args, **kwargs):
            return {"choices": [{"message": {"content": "Farver: blå"}}]}
        monkeypatch.setattr("jarvis.agent.call_ollama", mock_call_ollama)

        text = "Colors: blue"
        result = _translate_to_danish_if_needed(text)
        assert result == "Farver: blå"