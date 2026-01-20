"""File and download handling skill (delegated from agent)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, Optional

from jarvis import tools
from jarvis.files import (
    UPLOAD_DIR_NAME,
    create_download_token,
    delete_download_token,
    delete_all_download_tokens,
    delete_upload,
    delete_uploads_by_ext,
    delete_uploads_by_name,
    find_upload_by_name,
    keep_upload,
    list_download_tokens,
    list_uploads,
    read_upload_text,
    save_generated_text,
    save_upload,
)
from jarvis.session_store import (
    add_message,
    clear_pending_file,
    clear_pending_image_preview,
    get_last_image_prompt,
    set_last_image_prompt,
    set_pending_file,
    set_pending_image_preview,
)
from jarvis.db import get_conn


def _get_setting_value(key: str, default: str = "") -> str:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row and row["value"] is not None:
                return str(row["value"])
    except Exception:
        pass
    return default


def _make_download_link(user_id_int: int | None, session_id: str | None, filename: str, delete_on_download: bool) -> str:
    base_url = _get_setting_value("public_base_url", "").strip().rstrip("/")
    if not user_id_int:
        return f"{base_url}/files/{filename}" if base_url else f"/files/{filename}"
    token = create_download_token(
        user_id_int,
        filename,
        delete_file=delete_on_download,
        max_downloads=1,
        expires_minutes=1440,
    )
    path = f"/d/{token}"
    return f"{base_url}{path}" if base_url else path


def _download_notice() -> str:
    return "Linket er aktivt i 24 timer."


def _wrap_download_link(url: str) -> str:
    return f"[Download]({url})"


def _create_file_intent(prompt: str) -> tuple[str, str, bool] | None:
    p = prompt.lower()
    if not any(k in p for k in ["opret", "lav", "skab", "create", "ny fil"]):
        return None
    match = re.search(r"\b([a-z0-9_.-]+\.(txt|md|log))\b", prompt, flags=re.I)
    if not match:
        return None
    filename = match.group(1)
    content = None
    quoted = re.search(r"\"([^\"]+)\"|'([^']+)'", prompt)
    if quoted:
        content = quoted.group(1) or quoted.group(2)
    if not content:
        m = re.search(r"(?:tilføj|med)\s+(?:en\s+)?(?:kort\s+)?(.+?)\s*(?:tekst|indhold)", prompt, flags=re.I)
        if m:
            content = m.group(1)
            if not content:
                content = ""
            content = content.strip()
    delete_on_download = any(k in p for k in ["slet", "fjern"]) or "efter download" in p or "1 gang" in p or "en gang" in p
    return filename, content, delete_on_download


def _wants_download_link(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["download", "link", "send"])


def _generate_image_intent(prompt: str) -> str | None:
    p = prompt.lower()
    if not any(k in p for k in ["lav et billede", "generer et billede", "skab et billede", "billede af", "create an image", "make an image", "illustration af"]):
        return None
    match = re.search(r"\b(?:billede|illustration)\s+(?:af|med|om)\s+(.+)$", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"\b(?:lav|generer|skab)\s+(?:et\s+)?billede\s+af\s+(.+)$", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    return ""


def _file_type_intent(prompt: str) -> str | None:
    p = prompt.lower()
    if not any(k in p for k in ["filtype", "fil‑type", "hvilken slags fil", "hvad er det for en fil"]):
        return None
    match = re.search(r"\b([a-z0-9_.-]+\.[a-z0-9]+)\b", prompt, flags=re.I)
    if match:
        return match.group(1)
    return None


def _file_type_label(name: str) -> str:
    ext = os.path.splitext(name.lower())[1]
    mapping = {
        ".txt": "tekstfil",
        ".md": "Markdown‑tekst",
        ".log": "logfil",
        ".pdf": "PDF‑dokument",
        ".docx": "Word‑dokument",
        ".csv": "CSV‑regneark",
        ".json": "JSON‑datafil",
        ".png": "PNG‑billede",
        ".jpg": "JPEG‑billede",
        ".jpeg": "JPEG‑billede",
        ".gif": "GIF‑billede",
        ".svg": "SVG‑vektorgrafik",
        ".zip": "ZIP‑arkiv",
    }
    return mapping.get(ext, f"fil med endelsen {ext}" if ext else "ukendt filtype")


def _delete_ext_intent(prompt: str) -> str | None:
    p = prompt.lower()
    if "slet" not in p:
        return None
    match = re.search(r"\b\.?(png|jpg|jpeg|gif|svg)\b", p)
    if match:
        return match.group(1)
    return None


def _list_files_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["vis filer", "mine filer", "liste filer", "list filer", "list files", "show files"])


def _delete_file_intent(prompt: str) -> int | None:
    match = re.search(r"\bslet fil\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(1))
    return None


def _delete_file_by_name_intent(prompt: str) -> str | None:
    match = re.search(r"\bslet\s+(?:fil\s+)?([a-z0-9_.-]+\.(txt|md|pdf|docx|log))\b", prompt, flags=re.I)
    if match:
        return match.group(1)
    return None


def _list_download_links_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["download links", "download-link", "downloadlink", "aktive links", "aktive download", "aktive download links"])


def _delete_download_link_intent(prompt: str) -> str | None:
    match = re.search(r"\bslet\s+link\s+([a-z0-9]+)\b", prompt, flags=re.I)
    if match:
        return match.group(1)
    return None


def _delete_active_download_link_intent(prompt: str) -> bool:
    p = prompt.lower()
    return "slet" in p and "download" in p and "link" in p


def _delete_all_download_links_intent(prompt: str) -> bool:
    p = prompt.lower()
    return "slet alle download" in p or "slet alle links" in p or "slet alle download links" in p


def _keep_file_intent(prompt: str) -> int | None:
    match = re.search(r"\b(behold|forny)\s+fil\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(2))
    return None


def _analyze_file_intent(prompt: str) -> int | None:
    match = re.search(r"\banaly[sz]er\s+fil\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(1))
    return None


def handle_files(
    prompt: str,
    session_id: str | None,
    user_id: str,
    user_id_int: int | None,
    user_key: str,
    display_name: str,
    allowed_tools: list[str] | None,
    pending_file: Dict[str, Any] | None,
    pending_image_preview: Dict[str, Any] | None,
    reminders_due,
    should_attach_reminders: Callable[[str], bool],
    prepend_reminders: Callable[[str, Any, Any], str],
    affirm_intent: Callable[[str], bool],
    deny_intent: Callable[[str], bool],
    wants_previous_prompt: Callable[[str], bool],
) -> Optional[Dict[str, Any]]:
    """Handle file/download intents. Returns response dict or None."""
    # Pending overwrite
    if isinstance(pending_file, dict) and pending_file.get("awaiting_overwrite"):
        if affirm_intent(prompt):
            filename = pending_file.get("filename")
            content = pending_file.get("content") or ""
            delete_on_download = bool(pending_file.get("delete_on_download"))
            wants_link = bool(pending_file.get("wants_link"))
            if user_id_int and filename:
                existing = find_upload_by_name(user_id_int, filename)
                if existing:
                    delete_upload(user_id_int, user_key, existing["id"])
            info = save_generated_text(user_id_int, user_id, filename, content) if user_id_int else None
            rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}" if info else filename
            if wants_link:
                url = _make_download_link(user_id_int, session_id, rel_path, delete_on_download)
                reply = f"Som De ønsker. Filen er klar: {filename}.\nHer er download‑linket: {_wrap_download_link(url)}\n{_download_notice()}"
                if delete_on_download:
                    reply += "\nFilen slettes automatisk efter første download."
                data = {"type": "file", "title": filename, "label": "Download fil", "url": url}
                clear_pending_file(session_id)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            set_pending_file(
                session_id,
                json.dumps(
                    {
                        "awaiting_download": True,
                        "filename": filename,
                        "rel_path": rel_path,
                        "delete_on_download": delete_on_download,
                    },
                    ensure_ascii=False,
                ),
            )
            reply = f"Som De ønsker. Filen er klar: {filename}. Ønsker De et download‑link, eller skal jeg forberede den til noget bestemt?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if deny_intent(prompt):
            clear_pending_file(session_id)
            reply = "Som De ønsker. Jeg overskriver ikke filen."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Pending download
    if isinstance(pending_file, dict) and pending_file.get("awaiting_download"):
        if _generate_image_intent(prompt) is not None or _delete_ext_intent(prompt):
            clear_pending_file(session_id)
        else:
            filename = pending_file.get("filename")
            rel_path = pending_file.get("rel_path")
            delete_on_download = bool(pending_file.get("delete_on_download"))
            if user_id_int and ("slet" in prompt.lower()):
                target_name = _delete_file_by_name_intent(prompt) or filename
                if target_name:
                    removed = delete_uploads_by_name(user_id_int, user_key, target_name)
                    clear_pending_file(session_id)
                    reply = "Som De ønsker. Filen er slettet." if removed > 0 else "Jeg kan ikke finde den fil."
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if (affirm_intent(prompt) or _wants_download_link(prompt)) and filename and rel_path:
                url = _make_download_link(user_id_int, session_id, rel_path, delete_on_download)
                reply = f"Som De ønsker. Deres download‑link til {filename}:\n{_wrap_download_link(url)}\n{_download_notice()}"
                if delete_on_download:
                    reply += "\nFilen slettes automatisk efter første download."
                data = {"type": "file", "title": filename, "label": "Download fil", "url": url}
                clear_pending_file(session_id)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            if deny_intent(prompt):
                clear_pending_file(session_id)
                reply = "Som De ønsker. Intet download‑link. Ønsker De, at jeg gør noget andet med filen eller gemmer den til senere?"
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Pending image preview
    if isinstance(pending_image_preview, dict) and pending_image_preview.get("awaiting_preview"):
        if affirm_intent(prompt):
            rel_path = pending_image_preview.get("rel_path")
            filename = pending_image_preview.get("filename") or "billede"
            if user_id_int and rel_path:
                token = create_download_token(user_id_int, rel_path, delete_file=False, max_downloads=3, expires_minutes=60)
                url = f"/d/{token}"
                reply = f"Som De ønsker, {display_name}. Her er preview‑billedet."
                data = {"type": "image_preview", "title": filename, "url": url}
                clear_pending_image_preview(session_id)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            clear_pending_image_preview(session_id)
            reply = "Jeg kan ikke hente et preview af billedet lige nu."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if deny_intent(prompt):
            clear_pending_image_preview(session_id)
            reply = "Som De ønsker. Intet preview."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Latest upload quick download
    if session_id and user_id_int and _wants_download_link(prompt) and _generate_image_intent(prompt) is None and _delete_ext_intent(prompt) is None:
        items = list_uploads(user_id_int, limit=1)
        if items:
            info = items[0]
            rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}"
            url = _make_download_link(user_id_int, session_id, rel_path, False)
            reply = f"Som De ønsker. Deres download‑link:\n{_wrap_download_link(url)}\n{_download_notice()}"
            data = {"type": "file", "title": info.get("original_name") or "Fil", "label": "Download fil", "url": url}
            add_message(session_id, "assistant", reply)
            return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}

    # Delete active download link
    if session_id and _delete_active_download_link_intent(prompt) and user_id_int:
        items = list_download_tokens(user_id_int)
        if not items:
            reply = "Som De ønsker. Der er ingen aktive download‑links at slette."
        else:
            ok = delete_download_token(user_id_int, items[0]["token"])
            reply = "Som De ønsker. Download‑linket er slettet, og filen er bevaret." if ok else "Jeg kunne ikke slette linket."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # List download links
    if session_id and _list_download_links_intent(prompt) and user_id_int:
        items = list_download_tokens(user_id_int)
        if not items:
            reply = "Som De ønsker. Der er ingen aktive download‑links lige nu."
        else:
            lines = [
                f"{i['token'][:6]}… — {i.get('file_path')} — udløber {i.get('expires_at','')}"
                for i in items[:10]
            ]
            reply = "Som De ønsker. Aktive download‑links:\n" + "\n".join(lines)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Delete all links
    if session_id and _delete_all_download_links_intent(prompt) and user_id_int:
        removed = delete_all_download_tokens(user_id_int)
        reply = "Som De ønsker. Alle download‑links er slettet." if removed >= 0 else "Jeg kunne ikke slette links."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Delete download link by id
    token_id = _delete_download_link_intent(prompt)
    if session_id and token_id is not None and user_id_int:
        full_token = token_id
        items = list_download_tokens(user_id_int)
        for item in items:
            token = item.get("token") or ""
            if token.startswith(token_id):
                full_token = token
                break
        ok = delete_download_token(user_id_int, full_token)
        reply = "Som De ønsker. Download‑link slettet." if ok else "Jeg kan ikke finde det link."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Create file intent
    if session_id:
        create_req = _create_file_intent(prompt)
        if create_req:
            filename, content, delete_on_download = create_req
            wants_link = _wants_download_link(prompt)
            if user_id_int:
                existing = find_upload_by_name(user_id_int, filename)
                if existing:
                    set_pending_file(
                        session_id,
                        json.dumps(
                            {
                                "awaiting_overwrite": True,
                                "filename": filename,
                                "content": content,
                                "delete_on_download": delete_on_download,
                                "wants_link": wants_link,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    reply = f"Som De ønsker. Der findes allerede en fil med navnet {filename}. Vil du overskrive den?"
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            info = save_generated_text(user_id_int, user_id, filename, content) if user_id_int else None
            rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}" if info else filename
            if wants_link:
                url = _make_download_link(user_id_int, session_id, rel_path, delete_on_download)
                reply = f"Som De ønsker. Filen er klar: {filename}.\nHer er download‑linket: {_wrap_download_link(url)}\n{_download_notice()}"
                if delete_on_download:
                    reply += "\nFilen slettes automatisk efter første download."
                data = {"type": "file", "title": filename, "label": "Download fil", "url": url}
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            set_pending_file(
                session_id,
                json.dumps(
                    {
                        "awaiting_download": True,
                        "filename": filename,
                        "rel_path": rel_path,
                        "delete_on_download": delete_on_download,
                    },
                    ensure_ascii=False,
                ),
            )
            reply = f"Som De ønsker. Filen er klar: {filename}. Ønsker De et download‑link, eller skal jeg klargøre den til et bestemt formål?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Delete file by id
    if session_id:
        file_id = _delete_file_intent(prompt)
        if file_id is not None:
            ok = delete_upload(user_id_int, user_key, file_id) if user_id_int else False
            reply = "Som De ønsker. Filen er slettet." if ok else "Jeg kan ikke finde den fil."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        file_name = _delete_file_by_name_intent(prompt)
        if file_name is not None and user_id_int:
            removed = delete_uploads_by_name(user_id_int, user_key, file_name)
            reply = "Som De ønsker. Filen er slettet." if removed > 0 else "Jeg kan ikke finde den fil."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        keep_file_id = _keep_file_intent(prompt)
        if keep_file_id is not None:
            ok = keep_upload(user_id_int, keep_file_id) if user_id_int else False
            reply = "Filen er fornyet i 30 dage." if ok else "Kunne ikke finde den fil."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        analyze_file_id = _analyze_file_intent(prompt)
        if analyze_file_id is not None:
            info = read_upload_text(user_id_int, user_key, analyze_file_id) if user_id_int else None
            if not info:
                reply = "Jeg kan ikke finde den fil."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if info.get("error"):
                reply = info.get("detail", "Jeg kunne ikke analysere filen.")
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            messages = [
                {"role": "system", "content": "Analyser teksten kort og præcist på dansk. Ingen gæt."},
                {"role": "assistant", "content": info.get("text", "")},
                {"role": "user", "content": "Lav en kort analyse."},
            ]
            res = tools.call_ollama(messages)  # type: ignore[attr-defined]
            reply = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not reply:
                reply = "Jeg kunne ikke analysere filen lige nu."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # List files
    if session_id and _list_files_intent(prompt):
        items = list_uploads(user_id_int) if user_id_int else []
        if not items:
            reply = "Du har ingen filer endnu."
        else:
            lines = [f"{i['id']}. {i['original_name']} — udløber {i.get('expires_at','')}" for i in items[:10]]
            reply = "Dine filer:\n" + "\n".join(lines)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # File type intent
    if session_id and (file_name := _file_type_intent(prompt)):
        label = _file_type_label(file_name)
        reply = f"Som De ønsker. {file_name} er en {label}."
        if user_id_int:
            info = find_upload_by_name(user_id_int, file_name)
            if info:
                reply = f"Som De ønsker. {file_name} er en {label}, og den ligger på Deres filer."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Delete ext and maybe generate new image
    if session_id and user_id_int and (ext := _delete_ext_intent(prompt)):
        removed = delete_uploads_by_ext(user_id_int, user_key, ext)
        delete_msg = (
            f"Som De ønsker. Jeg har slettet {removed} .{ext} filer."
            if removed > 0
            else f"Som De ønsker. Jeg fandt ingen .{ext} filer at slette."
        )
        image_desc = _generate_image_intent(prompt)
        if wants_previous_prompt(prompt):
            image_desc = get_last_image_prompt(session_id) or image_desc
        if image_desc is None:
            add_message(session_id, "assistant", delete_msg)
            return {"text": delete_msg, "meta": {"tool": None, "tool_used": False}}
        if allowed_tools is not None and "image" not in allowed_tools:
            reply = delete_msg + "\nBilledværktøj er slået fra i denne session."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if not image_desc:
            reply = delete_msg + "\nHvad skal billedet forestille?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        result = tools.generate_image(image_desc)
        if not result or result.get("error"):
            detail = (result or {}).get("detail")
            reply = delete_msg + "\nJeg kunne ikke generere billedet lige nu."
            if detail:
                reply += f" ({detail})"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        filename = result.get("filename") or "image.png"
        content_type = result.get("content_type") or "image/png"
        data = result.get("bytes") or b""
        info = save_upload(user_id_int, user_id, filename, content_type, data)
        rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}"
        set_last_image_prompt(session_id, image_desc)
        wants_link = _wants_download_link(prompt)
        if wants_link:
            url = _make_download_link(user_id_int, session_id, rel_path, False)
            reply = (
                delete_msg
                + f"\nBilledet er klar: {filename}.\nHer er download‑linket: {_wrap_download_link(url)}\n{_download_notice()}"
            )
            add_message(session_id, "assistant", reply)
            return {
                "text": reply,
                "data": {"type": "image", "title": filename, "url": url},
                "meta": {"tool": None, "tool_used": False},
            }
        reply = delete_msg + "\nBilledet er klar."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # General image generation intent
    if session_id:
        image_desc = _generate_image_intent(prompt)
        if image_desc is not None:
            if allowed_tools is not None and "image" not in allowed_tools:
                reply = "Som De ønsker. Billedværktøj er slået fra i denne session."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if wants_previous_prompt(prompt):
                image_desc = get_last_image_prompt(session_id) or image_desc
            if not image_desc:
                reply = "Som De ønsker. Hvad skal billedet forestille?"
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            result = tools.generate_image(image_desc)
            if not result or result.get("error"):
                detail = (result or {}).get("detail")
                reply = "Jeg kunne ikke generere billedet lige nu."
                if detail:
                    reply += f" ({detail})"
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if not user_id_int:
                reply = "Jeg kan ikke gemme billedet uden en bruger."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            filename = result.get("filename") or "image.png"
            content_type = result.get("content_type") or "image/png"
            data = result.get("bytes") or b""
            info = save_upload(user_id_int, user_id, filename, content_type, data)
            rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}"
            set_last_image_prompt(session_id, image_desc)
            wants_link = _wants_download_link(prompt)
            if wants_link:
                url = _make_download_link(user_id_int, session_id, rel_path, False)
                reply = f"Som De ønsker. Billedet er klar: {filename}.\nHer er download‑linket: {_wrap_download_link(url)}\n{_download_notice()}"
                add_message(session_id, "assistant", reply)
                return {
                    "text": reply,
                    "data": {"type": "image", "title": filename, "url": url},
                    "meta": {"tool": None, "tool_used": False},
                }
            set_pending_file(
                session_id,
                json.dumps(
                    {
                        "awaiting_download": True,
                        "filename": filename,
                        "rel_path": rel_path,
                        "delete_on_download": False,
                    },
                    ensure_ascii=False,
                ),
            )
            reply = f"Som De ønsker. Billedet er klar: {filename}. Ønsker De et download‑link, eller skal jeg lave en variation?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Analyze image by name
    analyze_image_name = None
    match = re.search(r"\banaly[sz]er\s+(?:billede|image)\s+([a-z0-9_.-]+)\b", prompt, flags=re.I)
    if match:
        analyze_image_name = match.group(1)
    if session_id and analyze_image_name is not None:
        if allowed_tools is not None and "image" not in allowed_tools:
            reply = "Som De ønsker. Billedværktøj er slået fra i denne session."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if not user_id_int:
            reply = "Jeg kan ikke finde billedet."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        info = find_upload_by_name(user_id_int, analyze_image_name)
        if not info:
            reply = "Jeg kan ikke finde billedet."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        rel_path = f"{UPLOAD_DIR_NAME}/{info['stored_name']}"
        token = create_download_token(user_id_int, rel_path, delete_file=False, max_downloads=3, expires_minutes=60)
        url = f"/d/{token}"
        set_pending_image_preview(
            session_id,
            json.dumps({"awaiting_preview": True, "rel_path": rel_path, "filename": analyze_image_name}, ensure_ascii=False),
        )
        reply = "Vil du se et preview af billedet?"
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None


__all__ = [
    "handle_files",
    "_make_download_link",
    "_download_notice",
    "_wrap_download_link",
    "_create_file_intent",
    "_wants_download_link",
    "_generate_image_intent",
    "_file_type_intent",
    "_file_type_label",
    "_delete_ext_intent",
    "_list_files_intent",
    "_delete_file_intent",
    "_delete_file_by_name_intent",
    "_list_download_links_intent",
    "_delete_download_link_intent",
    "_delete_active_download_link_intent",
    "_delete_all_download_links_intent",
    "_keep_file_intent",
    "_analyze_file_intent",
]
