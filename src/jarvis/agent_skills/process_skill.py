"""
Process skill handler - thin wrapper for process/system/ping intents.
"""

import re
import json
from typing import Callable, Optional


def _butler_prefix(display_name: str | None) -> str:
    return f"{display_name or 'Butler'}:"


def _process_action(prompt: str) -> str:
    p = prompt.lower()
    if any(k in p for k in ["dræb", "stop", "afslut", "kill"]):
        return "kill"
    if any(k in p for k in ["find", "søg"]):
        return "find"
    return "list"


def _process_confirm_intent(prompt: str) -> bool:
    p = prompt.lower()
    return "bekræft" in p or "ja dræb" in p or "ja, dræb" in p


def _process_analysis_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(
        k in p
        for k in [
            "analys",
            "beskriv",
            "hvad er",
            "hvad gør",
            "forklar",
            "hvad laver",
            "identificer",
        ]
    )


def _find_process_match(prompt: str, items: list[dict]) -> dict | None:
    # Local import to avoid circular dependencies
    from jarvis.agent import _extract_pid

    p = prompt.lower()
    pid = _extract_pid(prompt)
    if pid:
        for i in items:
            if i.get("pid") == pid:
                return i
    for i in items:
        name = (i.get("name") or "").lower()
        if name and name in p:
            return i
    return None


def _system_fields_from_prompt(prompt: str) -> dict:
    p = (prompt or "").lower()
    wants_cpu = "cpu" in p
    wants_mem = any(k in p for k in ["ram", "hukommelse", "memory"])
    wants_disk = any(k in p for k in ["disk", "lagring", "storage"])
    wants_ip = any(k in p for k in ["ip", "netværk", "netvaerk"])
    wants_all = any(k in p for k in ["system", "ressourcer"])
    if not any([wants_cpu, wants_mem, wants_disk, wants_ip]) or wants_all:
        wants_cpu = wants_mem = wants_disk = wants_ip = True
    wants_all_ips = any(k in p for k in ["alle ip", "alle ip'er", "alle ips"])
    return {
        "cpu": wants_cpu,
        "mem": wants_mem,
        "disk": wants_disk,
        "ip": wants_ip,
        "all_ips": wants_all_ips,
    }


def _format_system_info(info: dict, prompt: str) -> str:
    cpu = info.get("cpu_percent")
    mem = info.get("memory") or {}
    disk = info.get("disk") or {}
    ip = info.get("ip") or {}
    fields = _system_fields_from_prompt(prompt)
    lines = []
    if fields["cpu"] and cpu is not None:
        lines.append(f"CPU load: {cpu}%")
    if fields["mem"] and mem:
        lines.append(
            f"Memory: {mem.get('used_mb')} MB brugt / {mem.get('total_mb')} MB total "
            f"(buffered: {mem.get('buffered_mb')} MB)"
        )
    if fields["disk"] and disk:
        lines.append(
            f"Disk ({disk.get('mount')}): {disk.get('used_gb')} GB i brug / {disk.get('total_gb')} GB total "
            f"(fri: {disk.get('free_gb')} GB)"
        )
    if fields["ip"]:
        local_ip = ip.get("local_ip")
        if local_ip:
            lines.append(f"Lokal IP: {local_ip}")
        if fields["all_ips"] and ip.get("all_ips"):
            lines.append(f"Alle IP'er: {', '.join(ip.get('all_ips'))}")
    return "\n".join(lines) if lines else "Jeg kan ikke hente systeminfo lige nu."


def _ping_result_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(
        k in p
        for k in [
            "sidste ping",
            "seneste ping",
            "ping resultat",
            "pingresultat",
            "vis ping",
            "vis resultatet for ping",
            "resultatet for de pings",
        ]
    )


def _ping_count_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(
        k in p
        for k in [
            "hvor mange ping",
            "hvor mange pings",
            "antal ping",
            "hvor mange sendte du",
            "hvor mange svar",
        ]
    )


def handle_process(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
    tool: str | None = None,
    tool_result: dict | None = None,
    reminders_due: list | None = None,
    user_id_int: int | None = None,
    display_name: str | None = None,
    resume_prompt: str | None = None,
    conversation_state=None,
    set_conversation_state_fn: Optional[Callable[[str], None]] = None,
):
    """
    Handle process/system/ping intents and tool results.
    Returns a response dict with 'text' and 'meta', or None if not handled.
    """
    # Local imports to avoid circular dependencies
    from jarvis.session_store import add_message
    from jarvis.memory import add_memory
    from jarvis.agent import (
        _should_attach_reminders, _prepend_reminders, _load_state, get_process_state, set_process_state,
        get_last_tool, set_last_tool, _safe_create_ticket
    )
    from jarvis.tools import kill_process

    # Handle intents (when tool_result is None)
    if tool_result is None:
        # Pending process confirm
        if session_id:
            pending_process = _load_state(get_process_state(session_id))
            pending_pid = pending_process.get("pid") if isinstance(pending_process, dict) else None
            if pending_pid and _process_confirm_intent(prompt):
                tool_result_kill = kill_process(int(pending_pid))
                set_process_state(session_id, "")
                reply = "Proces afsluttet." if tool_result_kill.get("ok") else "Jeg kunne ikke afslutte processen."
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_memory("assistant", reply, user_id=user_id)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": tool_result_kill, "meta": {"tool": "process", "tool_used": True}}

        # Ping result intent
        if session_id and _ping_result_intent(prompt):
            last = _load_state(get_last_tool(session_id))
            if not last or last.get("tool") != "ping":
                if user_id_int:
                    detail = f"Ingen ping‑resultat.\nPrompt: {prompt}"
                    _safe_create_ticket(user_id_int, "Manglende ping‑resultat", detail, "moderat")
                reply = "Jeg har ingen tidligere ping‑resultater at vise."
            else:
                host = last.get("host") or "host"
                success = bool(last.get("success"))
                wants_summary_only = bool(re.search(r"\b(vis|resultat|statistik)\b", prompt.lower()))
                reply = ""
                if not wants_summary_only:
                    reply = f"Ja, {host} svarer." if success else f"Nej, {host} svarer ikke."
                    reply += " "
                reply += (
                    f"Ping {host} {'lykkedes' if success else 'fejlede'}: "
                    f"{last.get('loss_percent')}% pakketab, {last.get('avg_ms')} ms."
                )
                try:
                    if float(last.get("avg_ms") or 0) >= 100:
                        reply += " Bemærk: Det er høj latency."
                except Exception:
                    pass
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": "ping", "tool_used": False}}

        # Ping count intent
        if session_id and _ping_count_intent(prompt):
            last = _load_state(get_last_tool(session_id))
            if not last or last.get("tool") != "ping":
                if user_id_int:
                    detail = f"Ingen ping‑kontekst.\nPrompt: {prompt}"
                    _safe_create_ticket(user_id_int, "Manglende ping‑kontekst", detail, "moderat")
                reply = "Jeg har ingen tidligere ping‑data at tælle."
            else:
                host = last.get("host") or "host"
                sent = last.get("sent")
                received = last.get("received")
                if sent is None or received is None:
                    reply = f"Jeg sendte 5 ping til {host}."
                else:
                    reply = f"Jeg sendte {sent} ping til {host}, og {received} svar kom tilbage."
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": "ping", "tool_used": False}}

        return None  # No intent handled

    # Handle tool results
    if tool == "process":
        if not isinstance(tool_result, dict) or tool_result.get("error"):
            reply = "Jeg kan ikke hente processer lige nu."
        elif tool_result.get("type") == "kill":
            reply = "Proces afsluttet." if tool_result.get("ok") else "Jeg kunne ikke afslutte processen."
        else:
            items = tool_result.get("items", [])
            if not items:
                reply = "Ingen processer fundet."
            else:
                sorted_items = sorted(items, key=lambda x: x.get("cpu", 0), reverse=True)
                match = _find_process_match(prompt, items)
                if match and _process_analysis_intent(prompt):
                    name = match.get("name") or "processen"
                    pid = match.get("pid")
                    cpu = match.get("cpu")
                    details = {
                        "uvicorn": "Uvicorn er en ASGI‑server, typisk brugt til FastAPI‑apps.",
                        "ollama": "Ollama er model‑serveren, der kører LLM‑inference lokalt.",
                        "firefox": "Firefox er en webbrowser.",
                        "code": "VS Code er en editor/IDE.",
                        "python": "Python er fortolkeren, som kører scripts og services.",
                        "node": "Node.js kører JavaScript‑services.",
                        "postgres": "PostgreSQL er en database‑server.",
                        "redis": "Redis er en hurtig nøgle‑/værdi‑database.",
                        "docker": "Docker kører containere og relaterede processer.",
                        "nginx": "Nginx er en webserver/reverse proxy.",
                        "gnome-shell": "GNOME Shell er skrivebordsmiljøets proces.",
                    }
                    desc = details.get((name or "").lower(), "Det er en systemproces/applikation.")
                    ownership = "Det ligner sandsynligvis Jarvis‑serveren her på maskinen." if (name or "").lower() == "uvicorn" else "Ud fra navnet alene kan jeg ikke bekræfte ejerskab."
                    reply = (
                        f"Som De ønsker. {name} (PID {pid}) bruger {cpu}% CPU.\n"
                        f"{desc}\n{ownership}"
                    )
                else:
                    top = sorted_items[0]
                    head = f"Jeg bemærker, at {top['name']} (PID {top['pid']}) ligger højest med {top['cpu']}% CPU."
                    lines = [
                        f"{i['pid']} {i['name']} — CPU {i['cpu']}% • MEM {i['mem']}%"  
                        for i in sorted_items[:5]
                    ]
                    reply = f"{head}\n\nTop 5 processer:\n" + "\n".join(lines)
        if resume_prompt:
            reply += f"\n\n{resume_prompt}"
        if session_id:
            last_payload = {"tool": "process", "source": "system_process"}
            set_last_tool(session_id, json.dumps(last_payload, ensure_ascii=False))
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", reply)
        return {"text": reply, "data": tool_result, "meta": {"tool": "process", "tool_used": True}}

    if tool == "system":
        if not isinstance(tool_result, dict) or tool_result.get("error"):
            reply = "Jeg kan ikke hente systeminfo lige nu."
        else:
            reply = _format_system_info(tool_result, prompt)
        reply = f"{_butler_prefix(display_name)}\n{reply}"
        if resume_prompt:
            reply += f"\n\n{resume_prompt}"
        if session_id:
            last_payload = {"tool": "system", "source": "system_probe"}
            set_last_tool(session_id, json.dumps(last_payload, ensure_ascii=False))
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", reply)
        return {"text": reply, "data": tool_result, "meta": {"tool": "system", "tool_used": True}}

    if tool == "ping":
        if not isinstance(tool_result, dict) or tool_result.get("error"):
            reply = "Jeg kan ikke køre ping lige nu. Angiv et hostnavn eller IP."
        else:
            host = tool_result.get("host")
            success = bool(tool_result.get("success"))
            wants_details = bool(re.search(r"\b(detaljer|resultat|pinget|statistik|ms|latens)\b", prompt.lower()))
            if success:
                reply = f"Ja, {host} svarer."
            else:
                reply = f"Nej, {host} svarer ikke."
            if wants_details:
                status = "lykkedes" if success else "fejlede"
                reply += (
                    f" Ping {host} {status}: "
                    f"{tool_result.get('loss_percent')}% pakketab, {tool_result.get('avg_ms')} ms."
                )
        if resume_prompt:
            reply += f"\n\n{resume_prompt}"
        if session_id:
            last_payload = {
                "tool": "ping",
                "source": "system_ping",
                "host": tool_result.get("host") if isinstance(tool_result, dict) else None,
                "success": tool_result.get("success") if isinstance(tool_result, dict) else None,
                "loss_percent": tool_result.get("loss_percent") if isinstance(tool_result, dict) else None,
                "avg_ms": tool_result.get("avg_ms") if isinstance(tool_result, dict) else None,
                "sent": tool_result.get("sent") if isinstance(tool_result, dict) else None,
                "received": tool_result.get("received") if isinstance(tool_result, dict) else None,
            }
            set_last_tool(session_id, json.dumps(last_payload, ensure_ascii=False))
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", reply)
        return {"text": reply, "data": tool_result, "meta": {"tool": "ping", "tool_used": True}}

    if tool == "process":
        if isinstance(tool_result, dict) and tool_result.get("success"):
            reply = f"Process søgning: {tool_result}"
        else:
            reply = "Ukendt proces handling."

        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": "process", "tool_used": True}}

    return None
