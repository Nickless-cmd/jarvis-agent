"""
UX copy and tone improvements for Jarvis.
Provides bilingual (da/en) natural language messages.
"""

from typing import Dict, Any


# Message templates
MESSAGES: Dict[str, Dict[str, str]] = {
    "model_timeout": {
        "da": "Modellen tog for lang tid at svare. Prøv igen med et kortere spørgsmål.",
        "en": "The model took too long to respond. Try again with a shorter question."
    },
    "empty_reply": {
        "da": "Jeg fik et tomt svar fra modellen. Kan du prøve at stille spørgsmålet anderledes?",
        "en": "I got an empty response from the model. Can you try rephrasing your question?"
    },
    "tool_failed": {
        "da": "{tool} fejlede. Prøv igen senere, eller brug en anden tilgang.",
        "en": "{tool} failed. Try again later, or use a different approach."
    },
    "weather_city_missing": {
        "da": "Jeg mangler en by eller postnummer for vejret. Prøv fx 'vejret i København'.",
        "en": "I need a city or postal code for the weather. Try 'weather in Copenhagen'."
    },
    "news_no_results": {
        "da": "Jeg kunne ikke finde nyheder lige nu. Prøv at søge efter noget specifikt.",
        "en": "I couldn't find any news right now. Try searching for something specific."
    },
    "search_no_results": {
        "da": "Ingen resultater fundet. Prøv at ændre søgeordene.",
        "en": "No results found. Try changing your search terms."
    },
    "file_not_found": {
        "da": "Filen blev ikke fundet. Tjek stien og prøv igen.",
        "en": "File not found. Check the path and try again."
    },
    "permission_denied": {
        "da": "Ingen adgang. Sørg for at du har de nødvendige tilladelser.",
        "en": "Permission denied. Make sure you have the necessary permissions."
    },
    "network_error": {
        "da": "Netværksfejl. Tjek din forbindelse og prøv igen.",
        "en": "Network error. Check your connection and try again."
    },
    "reminder_set": {
        "da": "Påmindelse sat til {time}. Jeg giver dig besked.",
        "en": "Reminder set for {time}. I'll notify you."
    },
    "note_saved": {
        "da": "Note gemt. Du kan se den med 'vis noter'.",
        "en": "Note saved. You can view it with 'show notes'."
    },
    "memory_remembered": {
        "da": "Jeg husker det.",
        "en": "I'll remember that."
    },
    "memory_forgotten": {
        "da": "Hvis du vil glemme noget specifikt, fortæl mig hvad.",
        "en": "If you want to forget something specific, tell me what."
    },
    "memory_cleared": {
        "da": "Din hukommelse er ryddet.",
        "en": "Your memory has been cleared."
    },
    "session_prompt_updated": {
        "da": "Personlighed opdateret.",
        "en": "Personality updated."
    },
    "session_prompt_reset": {
        "da": "Personlighed nulstillet til standard.",
        "en": "Personality reset to default."
    },
    "farewell": {
        "da": "Tak for i dag. Vi ses snart!",
        "en": "Thanks for today. See you soon!"
    },
    "welcome_back": {
        "da": "Velkommen tilbage! Hvordan kan jeg hjælpe?",
        "en": "Welcome back! How can I help?"
    }
}


def ux_error(message_key: str, ui_lang: str = "da", **kwargs) -> str:
    """
    Get a user-friendly error message.
    """
    lang = ui_lang.lower()[:2] if ui_lang else "da"
    lang = lang if lang in ["da", "en"] else "da"
    
    template = MESSAGES.get(message_key, {}).get(lang, f"Error: {message_key}")
    return template.format(**kwargs)


def ux_notice(message_key: str, ui_lang: str = "da", **kwargs) -> str:
    """
    Get a user-friendly notice/info message.
    """
    lang = ui_lang.lower()[:2] if ui_lang else "da"
    lang = lang if lang in ["da", "en"] else "da"
    
    template = MESSAGES.get(message_key, {}).get(lang, f"Notice: {message_key}")
    return template.format(**kwargs)