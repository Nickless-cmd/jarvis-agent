"""Vision and policy helpers factored out of the main agent module."""

from __future__ import annotations

import os
import re
import requests
from typing import Callable

from jarvis.agent_policy.language import _should_translate_vision_response


def _get_debug() -> Callable[[str], None]:
    """Lazy importer to avoid circular imports when debug logging is needed."""
    try:
        from jarvis.agent import _debug  # type: ignore

        return _debug
    except Exception:
        return lambda msg: None


def _ollama_base_url() -> str:
    base = os.getenv("OLLAMA_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    url = os.getenv("OLLAMA_URL", "").strip()
    if url:
        base = url.split("/v1/")[0].split("/api/")[0]
        return base.rstrip("/")
    return "http://127.0.0.1:11434"


def _translate_to_danish_if_needed(text: str) -> str:
    messages = [
        {"role": "system", "content": "Oversæt til dansk. Bevar fakta og betydning. Svar kun med oversættelsen."},
        {"role": "user", "content": text},
    ]
    try:
        from jarvis.agent import call_ollama  # type: ignore
    except Exception:
        return text

    res = call_ollama(messages)
    if res.get("error") or not res.get("choices"):
        return text
    translated = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not translated:
        return text
    return translated


def _looks_like_refusal(text: str) -> bool:
    low = text.lower()
    return any(
        bad in low
        for bad in [
            "kunne ikke",
            "kan ikke",
            "could not",
            "couldn't",
            "can't",
            "unable",
            "cannot",
            "could not help",
            "couldn't help",
        ]
    )


def _looks_like_guess(text: str) -> bool:
    low = text.lower()
    return any(
        guess in low
        for guess in [
            "som om",
            "måske",
            "ligner",
            "ser ud til",
            "muligvis",
            "tyder på",
            "kan være",
            "det kunne være",
            "det er som om",
            "turist",
            "rejse",
            "ferie",
            "eventyr",
            "oplevelse",
            "følelse",
            "føles",
            "attraktiv",
            "smuk",
            "overraskende",
            "tilføjer",
            "fremhæve",
            "kan bevises",
            "bevises",
        ]
    )


def _validate_vision_format(text: str, lang: str) -> tuple[bool, str | None]:
    """
    Validate the expected 5-line structured vision output.
    Returns (ok, error_message_or_none).
    """
    lines = [line.lstrip("*- ").strip() for line in text.strip().split("\n") if line.strip()]
    if len(lines) != 5:
        return False, f"Forventede 5 linjer, fandt {len(lines)}"

    if lang.startswith("da"):
        expected_labels = ["Farver:", "Former:", "Objekter:", "Antal:", "Placering:"]
    else:
        expected_labels = ["Colors:", "Shapes:", "Objects:", "Count:", "Position:"]

    for i, line in enumerate(lines):
        expected = expected_labels[i]
        if not line.startswith(expected):
            return False, f"Linje {i+1}: Forventede '{expected}', fandt '{line[:30]}...'"

        after_colon = line[len(expected) :].strip()
        if not after_colon:
            return False, f"Linje {i+1}: Manglende værdi efter '{expected}'"

    return True, None


def _violates_vision_policy(text: str, lang: str) -> tuple[bool, str | None]:
    """
    Line-based policy validation. Returns (violates, reason_or_none).
    """
    lines = [line.lstrip("*- ").strip() for line in text.strip().split("\n") if line.strip()]
    if len(lines) != 5:
        return False, None  # Let format validation handle this

    uncertain_word = "usikkert" if lang.startswith("da") else "uncertain"

    forbidden_env = [
        "fjord",
        "kyst",
        "klippe",
        "klinter",
        "bjerg",
        "bjerge",
        "ocean",
        "hav",
        "sø",
        "strand",
        "skov",
        "dal",
        "by",
        "vej",
        "bro",
        "norge",
        "danmark",
        "københavn",
        "paris",
        "london",
        "new york",
        "tokyo",
        "berlin",
    ]

    forbidden_activities = [
        "sejler",
        "sejler på",
        "ferie",
        "turist",
        "vacation",
        "idyl",
        "idylisk",
        "idyllic",
        "holiday",
        "måske",
        "ligner",
        "ser ud til",
        "possibly",
        "looks like",
        "seems",
        "maybe",
    ]

    allowed_shapes = [
        "rektangel",
        "rektangler",
        "kvadrat",
        "firkant",
        "cirkel",
        "trekant",
        "oval",
        "ellipse",
        "linje",
        "linjer",
        "kurve",
        "kurver",
        "rectangle",
        "rectangles",
        "square",
        "circle",
        "triangle",
        "oval",
        "ellipse",
        "line",
        "lines",
        "curve",
        "curves",
    ]

    for i, line in enumerate(lines):
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        label = line[:colon_idx].strip()
        value = line[colon_idx + 1 :].strip().lower()

        if value == uncertain_word:
            continue

        if "former" in label.lower() or "shapes" in label.lower():
            words = re.findall(r"\b\w+\b", value)
            for word in words:
                if word not in allowed_shapes and word != uncertain_word:
                    return True, f"'{word}' er ikke en tilladt form i '{label}'"

        elif "objekter" in label.lower() or "objects" in label.lower():
            for word in forbidden_env:
                if word in value:
                    return True, f"Miljøfortolkning '{word}' ikke tilladt i '{label}'"

        elif "placering" in label.lower() or "position" in label.lower():
            allowed_pos = [
                "øverst",
                "nederst",
                "venstre",
                "højre",
                "centrum",
                "forgrund",
                "baggrund",
                "nær kanten",
                "midt i billedet",
                "top",
                "bottom",
                "left",
                "right",
                "center",
                "foreground",
                "background",
                "near edge",
                "middle of image",
            ]
            words = re.findall(r"\b\w+\b", value)
            for word in words:
                if word not in allowed_pos and word != uncertain_word:
                    return True, f"Position '{word}' ikke tilladt i '{label}'"

        for word in forbidden_env + forbidden_activities:
            if word in value:
                return True, f"Forbudt ord '{word}' i '{label}'"

    return False, None


def _looks_like_hallucination(text: str) -> bool:
    """Extended hallucination detection for vision responses."""
    low = text.lower().strip()
    debug = _get_debug()

    if _looks_like_refusal(text) or _looks_like_guess(text):
        return True

    words = low.split()
    if len(words) <= 2:
        meaningless_responses = [
            "godsmærke",
            "brand",
            "mærke",
            "badge",
            "logo",
            "symbol",
            "icon",
            "test",
            "hej",
            "hello",
            "hi",
            "ok",
            "okay",
            "yes",
            "no",
            "billede",
            "image",
            "photo",
            "picture",
            "img",
            "pic",
            "ingen",
            "nothing",
            "empty",
            "blank",
            "void",
            "error",
            "fejl",
            "problem",
            "issue",
            "fail",
            "ukendt",
            "unknown",
            "undefined",
            "null",
            "none",
        ]
        if any(word in meaningless_responses for word in words):
            if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
                debug(f"🖼️ Meaningless short response detected: '{text}'")
            return True

        valid_short_descriptions = [
            "rektangel",
            "cirkel",
            "kvadrat",
            "linje",
            "punkt",
            "prik",
            "blå",
            "rød",
            "grøn",
            "gul",
            "sort",
            "hvid",
            "grå",
            "stort",
            "lille",
            "rundt",
            "firkantet",
            "langt",
            "kort",
            "lys",
            "mørk",
            "klar",
            "uskarp",
            "rectangle",
            "circle",
            "square",
            "line",
            "dot",
            "point",
            "blue",
            "red",
            "green",
            "yellow",
            "black",
            "white",
            "gray",
            "big",
            "small",
            "round",
            "square",
            "long",
            "short",
            "light",
            "dark",
            "clear",
            "blurry",
        ]
        if not any(word in valid_short_descriptions for word in words):
            if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
                debug(f"🖼️ Short response not describing image: '{text}'")
            return True

    wrong_language_indicators = [
        "det er ikke et bilde",
        "siden det ikke er",
        "er det ikke mulig",
        "rett frem",
        "tilbakemelding",
        "kvalitetsproblem",
        "bakgrunden",
        "konteksten",
        "skal jeg gerne hjælpe",
        "det är inte en bild",
        "sedan det inte er",
        "är det ikke muligt",
        "es ist kein bild",
        "c'est pas une image",
        "no es una imagen",
    ]

    if any(indicator in low for indicator in wrong_language_indicators):
        if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
            debug(f"🖼️ Wrong language detected in response: {text[:100]}...")
        return True

    avoidance_indicators = [
        "kan ikke analysere",
        "kan ikke se",
        "er det ikke mulig",
        "er det umulig",
        "kan ikke give",
        "er det svært",
        "er det komplekst",
        "cannot analyze",
        "cannot see",
        "is not possible",
        "is impossible",
        "cannot provide",
        "is difficult",
        "is complex",
        "kvalitetsproblem",
        "quality issue",
        "teknisk problem",
        "technical issue",
    ]

    if any(indicator in low for indicator in avoidance_indicators):
        description_indicators = [
            "der er",
            "der ses",
            "billedet viser",
            "på billedet",
            "there is",
            "there are",
            "the image shows",
            "in the image",
            "billedet indeholder",
            "billedet har",
            "image contains",
            "image has",
        ]
        if not any(indicator in low for indicator in description_indicators):
            if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
                debug(f"🖼️ Avoidance without description detected: {text[:100]}...")
            return True

    critical_hallucinations = [
        "københavn",
        "danmark",
        "europa",
        "amerika",
        "asien",
        "afrika",
        "paris",
        "london",
        "new york",
        "tokyo",
        "berlin",
        "rom",
        "familie",
        "venner",
        "kolleger",
        "turist",
        "arbejde",
        "fest",
        "begivenhed",
        "konference",
        "møde",
        "samtale",
        "glad",
        "trist",
        "sur",
        "bekymret",
        "nervøs",
        "spændt",
        "afslappet",
        "tænker",
        "overvejer",
        "planlægger",
        "husker",
        "drømmer",
        "elsker",
        "hader",
        "frygter",
        "håber",
        "ønsker",
        "i dag",
        "i går",
        "i morgen",
        "sidste uge",
        "næste år",
        "arbejder",
        "sover",
        "læser",
        "skriver",
        "taler",
        "lytter",
        "arbeider",
        "sover",
        "leser",
        "skriver",
        "taler",
        "lytter",
        "arbetar",
        "sover",
        "läser",
        "skriver",
        "talar",
        "lyssnar",
        "godsmærke",
        "brand",
        "mærke",
        "badge",
        "logo",
        "symbol",
        "icon",
        "test",
        "demo",
        "sample",
        "example",
        "placeholder",
    ]

    allowed_in_images = {
        "vand",
        "bjerge",
        "båd",
        "skyer",
        "himmel",
        "sol",
        "måne",
        "træer",
        "blomster",
        "hus",
        "bygning",
        "vej",
        "bro",
        "sten",
        "klippe",
        "strand",
        "hav",
        "sø",
        "flod",
        "skov",
        "rektangel",
        "cirkel",
        "kvadrat",
        "linje",
        "punkt",
        "prik",
        "form",
        "figur",
        "polygon",
        "oval",
        "ellipse",
        "blå",
        "rød",
        "grøn",
        "gul",
        "sort",
        "hvid",
        "grå",
        "brun",
        "orange",
        "lilla",
        "pink",
        "violet",
        "gylden",
        "sølv",
        "stor",
        "lille",
        "lang",
        "kort",
        "bred",
        "smal",
        "tynd",
        "tyk",
        "rund",
        "firkantet",
        "spids",
        "flad",
        "skrå",
        "lodret",
        "vandret",
        "glat",
        "ru",
        "blank",
        "mat",
        "gennemsigtig",
        "uigennemsigtig",
        "lys",
        "mørk",
        "skygge",
        "skyggelagt",
        "oplyst",
        "mørklagt",
        "klar",
        "uskarp",
        "skarp",
        "sløret",
        "øverst",
        "nederst",
        "venstre",
        "højre",
        "midt",
        "center",
        "foran",
        "bagved",
        "ved siden af",
        "mellem",
        "over",
        "under",
        "én",
        "to",
        "tre",
        "fire",
        "fem",
        "flere",
        "mange",
        "få",
        "person",
        "menneske",
        "ansigt",
        "øjne",
        "hånd",
        "arm",
        "ben",
        "bil",
        "cykel",
        "tog",
        "fly",
        "skib",
        "fisk",
        "fugl",
        "hund",
        "kat",
        "stol",
        "bord",
        "computer",
        "telefon",
        "bog",
        "glas",
        "tallerken",
        "billede",
        "foto",
        "billedet",
        "viser",
        "indeholder",
        "ses",
        "kan ses",
        "afbilder",
        "forestiller",
        "billedanalyse",
        "beskrivelse",
    }

    image_related_indicators = {
        "billede",
        "foto",
        "viser",
        "ses",
        "indeholder",
        "afbilder",
        "forestiller",
        "beskriver",
        "analyse",
        "farve",
        "form",
        "objekt",
        "figur",
        "størrelse",
        "position",
        "placering",
        "øverst",
        "nederst",
        "venstre",
        "højre",
        "midt",
        "foran",
        "bagved",
        "ved siden",
        "mellem",
        "over",
        "under",
    }
    has_image_indicators = any(word in low for word in image_related_indicators)
    has_allowed_words = any(word in low for word in allowed_in_images)
    has_critical_words = any(word in low for word in critical_hallucinations)

    if not has_image_indicators and not has_allowed_words:
        if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
            debug(f"🖼️ Response not related to image analysis: '{text}'")
        return True

    has_allowed_words = any(word in low for word in allowed_in_images)
    has_critical_words = any(word in low for word in critical_hallucinations)

    if has_critical_words and not has_allowed_words:
        return True

    return any(indicator in low for indicator in critical_hallucinations)


def _describe_image_ollama(b64: str, is_admin: bool, ui_lang: str | None) -> tuple[str | None, str | None]:
    model = os.getenv("OLLAMA_VISION_MODEL", "").strip()
    if not model:
        return None, "OLLAMA_VISION_MODEL mangler"
    lang = (ui_lang or "").lower()

    if lang.startswith("da"):
        prompt = (
            "BESKRIV KUN DET DU KAN SE DIREKTE I BILLEDET.\n\n"
            "SVARET SKAL HAVE PRÆCIS 5 LINJER I DETTE FORMAT (INGEN EKSTRA TEKST):\n"
            "Farver: ...\n"
            "Former: ...\n"
            "Objekter: ...\n"
            "Antal: ...\n"
            "Placering: ...\n\n"
            "REGLER:\n"
            "- Brug 'usikkert' hvis du ikke er 100% sikker.\n"
            "- INGEN stednavne, INGEN miljøfortolkninger (fjord, kyst, klippe, bjerg, hav, sø, strand, skov, dal, by, bygning, hus, vej, bro).\n"
            "- INGEN aktiviteter, INGEN gæt som 'ligner', 'måske', 'ser ud til'.\n"
            "- Former må kun være geometriske former: linjer, kurver, rektangler, cirkler, kvadrater, trekanter, ellipser.\n"
            "- Objekter må kun være konkrete genstande du kan se tydeligt.\n"
            "- Placering må kun bruge: øverst, nederst, venstre, højre, centrum, forgrund, baggrund, nær kanten, midt i billedet.\n"
            "- Hver linje skal have noget efter ':'."
        )
        strict_prompt = prompt + "\n\nHvis du er i tvivl, skriv 'usikkert'."
        ultra_strict_prompt = strict_prompt + "\n\nSæt 'usikkert' på alle felter du ikke er 100% sikker på."
    else:
        prompt = (
            "DESCRIBE ONLY WHAT YOU CAN SEE DIRECTLY IN THE IMAGE.\n\n"
            "THE ANSWER MUST HAVE EXACTLY 5 LINES IN THIS FORMAT (NO EXTRA TEXT):\n"
            "Colors: ...\n"
            "Shapes: ...\n"
            "Objects: ...\n"
            "Count: ...\n"
            "Position: ...\n\n"
            "RULES:\n"
            "- Use 'uncertain' if you are not 100% sure.\n"
            "- NO place names, NO environmental interpretations (fjord, coast, cliff, mountain, ocean, lake, beach, forest, valley, city, building, house, road, bridge).\n"
            "- NO activities, NO guesses like 'looks like', 'maybe', 'seems'.\n"
            "- Shapes may only be geometric shapes: lines, curves, rectangles, circles, squares, triangles, ellipses.\n"
            "- Objects may only be concrete items you can see clearly.\n"
            "- Position may only use: top, bottom, left, right, center, foreground, background, near edge, middle of image.\n"
            "- Each line must have something after ':'."
        )
        strict_prompt = prompt + "\n\nIf uncertain, write 'uncertain'."
        ultra_strict_prompt = strict_prompt + "\n\nSet 'uncertain' on all fields you are not 100% sure about."

    def _try_generate(payload, timeout):
        from jarvis.provider.ollama_client import ollama_request
        resp = ollama_request(url, payload, connect_timeout=5.0, read_timeout=timeout, retries=2)
        if not resp.get("ok"):
            err = resp.get("error") or {}
            return None, f"Ollama kunne ikke nås: {err.get('message','ukendt fejl')} (id: {err.get('trace_id','-')})"
        data = resp.get("data") or {}
        text = (data.get("response") or "").strip()
        if not text:
            return None, "Ollama returnerede tomt svar"
        return text, None

    ctx = int(os.getenv("OLLAMA_VISION_CTX", "2048"))
    num_gpu = os.getenv("OLLAMA_VISION_NUM_GPU")
    url = _ollama_base_url() + "/api/generate"
    debug = _get_debug()

    if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
        debug(f"🖼️ Image analysis request: model={model}, lang={lang}")

    for attempt in range(3):
        if attempt == 0:
            current_prompt = prompt
        elif attempt == 1:
            current_prompt = strict_prompt
        else:
            current_prompt = ultra_strict_prompt

        payload = {
            "model": model,
            "prompt": current_prompt,
            "images": [b64],
            "stream": False,
            "options": {"num_ctx": ctx, "num_predict": 200},
        }
        if num_gpu is not None:
            try:
                payload["options"]["num_gpu"] = int(num_gpu)
            except ValueError:
                pass

        text, err = _try_generate(payload, 30)
        if err:
            if attempt == 2:
                return None, err
            continue

        if not text:
            if attempt == 2:
                return None, "Ollama gav tomt svar"
            continue

        ok, err_msg = _validate_vision_format(text, lang)
        if not ok:
            if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
                debug(f"🖼️ Attempt {attempt+1} format validation failed: {err_msg}")
            if attempt == 2:
                return None, f"Formatfejl i billedbeskrivelse: {err_msg}" if is_admin else "Billedbeskrivelsen er ugyldig."
            continue

        violates, reason = _violates_vision_policy(text, lang)
        if violates:
            if os.getenv("JARVIS_DEBUG_IMAGE", "0") == "1":
                debug(f"🖼️ Attempt {attempt+1} policy violation: {reason}")
            if attempt == 2:
                return None, f"Billedbeskrivelse indeholder usikre oplysninger: {reason}" if is_admin else "Billedbeskrivelsen er usikker."
            continue

        if lang.startswith("da") and _should_translate_vision_response(text, lang):
            text = _translate_to_danish_if_needed(text)
        return text, None

    return None, "Alle forsøg fejlede"


__all__ = [
    "_ollama_base_url",
    "_translate_to_danish_if_needed",
    "_looks_like_refusal",
    "_looks_like_guess",
    "_validate_vision_format",
    "_violates_vision_policy",
    "_looks_like_hallucination",
    "_describe_image_ollama",
]
