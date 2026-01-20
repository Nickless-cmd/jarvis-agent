"""
Memory manager for long-term memory in Jarvis.
Handles automatic writing and retrieval of user memories with categorization and redaction.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List

from jarvis.memory import add_memory, search_memory
from jarvis.agent_format.ux_copy import ux_notice

from jarvis.agent_format.ux_copy import ux_error, ux_notice


@dataclass
class MemoryItem:
    content: str
    category: str
    timestamp: str


def redact_sensitive(text: str) -> str:
    """
    Remove sensitive patterns like API keys, tokens, passwords, private identifiers.
    """
    # API keys (common patterns)
    text = re.sub(r'\b(api[_-]?key|apikey)\s*[:=]\s*[\w\-]{10,}', '[REDACTED]', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(token|bearer)\s*[:=]\s*[\w\-]{10,}', '[REDACTED]', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(password|pwd|pass)\s*[:=]\s*[^\'"\s]{3,}', '[REDACTED]', text, flags=re.IGNORECASE)
    
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Phone numbers (basic pattern)
    text = re.sub(r'\b\d{8,15}\b', '[PHONE]', text)
    
    # Credit card patterns (basic)
    text = re.sub(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b', '[CARD]', text)
    
    return text


def should_write_memory(prompt: str, reply: str, ui_lang: str = "da") -> List[MemoryItem]:
    """
    Determine if we should write memories from this interaction.
    Returns list of MemoryItem to store.
    """
    items = []
    
    # Only store if reply is substantial
    if len(reply.strip()) < 30:
        return items
    
    # Detect user preferences/facts
    prompt_lower = prompt.lower()
    reply_lower = reply.lower()
    
    # Preferences (likes, dislikes, settings)
    if any(word in prompt_lower for word in ["kan du huske", "jeg kan lide", "jeg elsker", "jeg hader", "foretrækker", "altid", "kan godt lide"]):
        redacted = redact_sensitive(reply)
        items.append(MemoryItem(
            content=redacted,
            category="preference",
            timestamp=datetime.now().isoformat()
        ))
    
    # Project context (work, tasks, setup)
    if any(word in prompt_lower for word in ["projekt", "arbejde", "opgave", "setup", "konfiguration", "kode", "udvikling", "arbejder"]):
        redacted = redact_sensitive(reply)
        items.append(MemoryItem(
            content=redacted,
            category="project",
            timestamp=datetime.now().isoformat()
        ))
    
    # Identity-lite (name, basic info, but not sensitive)
    if any(word in prompt_lower for word in ["jeg hedder", "mit navn er", "jeg er", "jeg arbejder", "jeg bor", "hedder"]):
        redacted = redact_sensitive(reply)
        items.append(MemoryItem(
            content=redacted,
            category="identity-lite",
            timestamp=datetime.now().isoformat()
        ))
    
    # TODO items
    if any(word in prompt_lower for word in ["husker", "påmind", "todo", "opgave", "skal jeg", "må ikke glemme", "påmindelse"]):
        redacted = redact_sensitive(reply)
        items.append(MemoryItem(
            content=redacted,
            category="todo",
            timestamp=datetime.now().isoformat()
        ))
    
    return items


def should_retrieve_memory(prompt: str, ui_lang: str = "da") -> bool:
    """
    Determine if we should retrieve memories for this prompt.
    """
    prompt_lower = prompt.lower()
    
    # Retrieve for personal questions
    if any(word in prompt_lower for word in ["husker du", "kan du huske", "hvad sagde jeg", "sidst", "tidligere", "husker"]):
        return True
    
    # Retrieve for context-dependent questions
    if any(word in prompt_lower for word in ["som før", "som sidst", "fortsæt", "videre"]):
        return True
    
    # Retrieve for preference questions
    if any(word in prompt_lower for word in ["foretrækker", "kan lide", "elsker", "hader", "kan du lide"]):
        return True
    
    return False


def retrieve_context(user_id: str, prompt: str, k: int = 6) -> str:
    """
    Retrieve relevant memories and format as short bullet points.
    """
    memories = search_memory(prompt, k=k, user_id=user_id)
    if not memories:
        return ""
    
    # Filter and shorten memories
    bullets = []
    for mem in memories:
        # Skip if too short or contains redacted content
        if len(mem) < 20 or '[REDACTED]' in mem:
            continue
        
        # Shorten to first sentence or 100 chars
        shortened = mem.split('.')[0][:100].strip()
        if shortened:
            bullets.append(f"• {shortened}")
    
    if not bullets:
        return ""
    
    return "Relevant memory:\n" + "\n".join(bullets[:4])  # Limit to 4 bullets


def handle_memory_commands(prompt: str, user_id: str, ui_lang: str = "da") -> str | None:
    """
    Handle user memory commands. Returns response if handled, None otherwise.
    """
    prompt_lower = prompt.lower().strip()
    
    if prompt_lower.startswith("husk dette") or prompt_lower.startswith("remember this"):
        content = prompt[11:].strip() if prompt_lower.startswith("husk dette") else prompt[14:].strip()
        if content:
            redacted = redact_sensitive(content)
            add_memory("user", f"User asked to remember: {redacted}", user_id)
            return ux_notice("memory_remembered", ui_lang)
        return "Hvad skal jeg huske?"
    
    if prompt_lower.startswith("glem det") or prompt_lower.startswith("forget that"):
        # This is tricky - we'd need to identify what to forget
        # For now, just acknowledge
        return ux_notice("memory_forgotten", ui_lang)
    
    if prompt_lower in ["vis hvad du husker om mig", "show what you remember about me", "hvad husker du om mig"]:
        memories = search_memory("user preferences identity", k=10, user_id=user_id)
        if not memories:
            return "Jeg har ikke gemt nogen personlige oplysninger om dig endnu."
        
        lines = ["Her er hvad jeg husker om dig:"]
        for mem in memories[:5]:
            if '[REDACTED]' not in mem:
                lines.append(f"• {mem[:100]}...")
        return "\n".join(lines)
    
    if prompt_lower in ["ryd hukommelse", "clear memory", "slet hukommelse"]:
        from jarvis.memory import purge_user_memory
        purge_user_memory(user_id)
        return ux_notice("memory_cleared", ui_lang)
    
    return None