"""
Freshness policy for agent responses.
Ensures Jarvis never claims outdated knowledge and prefers tools for time-sensitive queries.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo


def is_time_sensitive(prompt: str, ui_lang: str = "da") -> bool:
    """
    Determine if a prompt requires fresh information.
    """
    prompt_lower = prompt.lower().strip()
    
    # Danish keywords
    da_sensitive = [
        "seneste", "nyheder", "i dag", "for nylig", "opdateret", "pris nu", 
        "ceo nu", "valg", "lov nu", "aktuel", "lige nu", "nuværende",
        "2026", "2025", "2024", "2023", "2022", "2021", "2020",  # recent years
        "år", "måned", "uge", "dag",  # when combined with recent
    ]
    
    # English keywords
    en_sensitive = [
        "latest", "news", "today", "recently", "updated", "current price",
        "ceo now", "election", "law now", "current", "right now", "now",
        "2026", "2025", "2024", "2023", "2022", "2021", "2020",
        "year", "month", "week", "day",
    ]
    
    sensitive_keywords = da_sensitive if ui_lang.startswith("da") else en_sensitive
    
    # Check for keywords
    for keyword in sensitive_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check for date patterns like "2026-01-20" or "januar 2026"
    if re.search(r"\b(20\d{2})\b", prompt_lower):  # years 2000-2099
        return True
    
    # Check for "what is the date" type questions
    if detect_date_query(prompt):
        return True
    
    return False


def inject_time_context(ui_lang: str = "da") -> str:
    """
    Return a short system note with today's date and timezone.
    """
    now = datetime.now(ZoneInfo("Europe/Copenhagen"))
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    
    lang = ui_lang or "da"
    if lang.startswith("da"):
        return f"I dag er det {date_str}, klokken er {time_str} i Europa/København."
    else:
        return f"Today is {date_str}, the time is {time_str} in Europe/Copenhagen."


def detect_date_query(prompt: str) -> bool:
    """
    Detect if the prompt is asking for the current date or time.
    """
    prompt_lower = prompt.lower().strip()
    
    da_date_queries = [
        "hvilken dato er det", "hvad er datoen", "hvad er dagens dato",
        "hvilken dag er det", "hvad er klokken", "hvad tid er det",
    ]
    
    en_date_queries = [
        "what is the date", "what is today's date", "what day is it",
        "what time is it", "what is the current time",
    ]
    
    # Simple keyword matching
    for query in da_date_queries + en_date_queries:
        if query in prompt_lower:
            return True
    
    return False