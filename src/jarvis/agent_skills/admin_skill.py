"""
Admin skill handler - thin wrapper for admin-related intents.
"""

import sqlite3


def handle_admin(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle admin intents like creating users.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        _admin_create_user_from_prompt, register_user, add_memory, add_message, get_user_profile
    )

    profile = get_user_profile(user_id)
    is_admin_user = bool((profile or {}).get("is_admin"))

    if not is_admin_user:
        return None  # Not admin, skip

    payload, ask = _admin_create_user_from_prompt(prompt)
    if ask:
        add_memory("assistant", ask, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", ask)
        return {"text": ask, "meta": {"tool_used": False}}
    if payload:
        try:
            created = register_user(
                payload["username"],
                payload["password"],
                1 if payload["is_admin"] else 0,
                email=payload["email"],
                full_name=payload["full_name"],
                city=payload.get("city"),
            )
            reply = f"Bruger oprettet: {created['username']}."
        except sqlite3.IntegrityError:
            reply = "Brugernavn findes allerede. Vælg et andet."
        except Exception:
            reply = "Kunne ikke oprette brugeren lige nu."
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool_used": False}}

    return None  # No admin intent matched