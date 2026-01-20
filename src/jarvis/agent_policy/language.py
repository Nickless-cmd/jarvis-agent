"""Language helpers for the agent."""


def _should_translate_vision_response(text: str, ui_lang: str) -> bool:
    """
    Decide whether a vision response should be translated into Danish.
    Keeps existing behavior untouched.
    """
    if not ui_lang.startswith("da"):
        return False

    text_lower = text.strip().lower()

    # If it starts with Danish labels, it's already Danish
    if text.startswith("Farver:") or text.startswith("Former:") or text.startswith("Objekter:") or text.startswith("Antal:") or text.startswith("Placering:"):
        return False

    # If it starts with English labels, translation needed
    if text.startswith("Colors:") or text.startswith("Shapes:") or text.startswith("Objects:") or text.startswith("Count:") or text.startswith("Position:"):
        return True

    # Check for Danish vs English words
    danish_indicators = ["farver", "former", "objekter", "antal", "placering", "blå", "rød", "grøn", "gul", "sort", "hvid", "rektangel", "cirkel", "kvadrat", "usikkert"]
    english_indicators = ["colors", "shapes", "objects", "count", "position", "blue", "red", "green", "yellow", "black", "white", "rectangle", "circle", "square", "uncertain"]

    danish_count = sum(1 for word in danish_indicators if word in text_lower)
    english_count = sum(1 for word in english_indicators if word in text_lower)

    # If more Danish indicators, assume it's Danish
    if danish_count > english_count:
        return False

    # If more English or equal, translate if lang is Danish
    return True


__all__ = ["_should_translate_vision_response"]

