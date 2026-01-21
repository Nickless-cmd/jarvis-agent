"""
Lightweight performance metrics and context budget management.
"""

import time
import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from jarvis.db import get_conn


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single request."""
    user_id: str
    session_id: Optional[str]
    timestamp: str
    
    # Timings (milliseconds)
    memory_retrieval_ms: float = 0.0
    tool_calls_total_ms: float = 0.0
    llm_call_ms: float = 0.0
    total_request_ms: float = 0.0
    
    # Context budget info
    context_items: Dict[str, int] = None  # e.g., {"history_messages": 5, "memory_snippets": 3}
    context_chars: int = 0
    budget_exceeded: bool = False
    items_trimmed: int = 0
    
    # Tool details
    tool_calls: List[Dict[str, Any]] = None  # [{"name": "weather", "latency_ms": 150.5, "success": True}]
    
    def __post_init__(self):
        if self.context_items is None:
            self.context_items = {}
        if self.tool_calls is None:
            self.tool_calls = []


class ContextBudget:
    """Context budget configuration and enforcement."""
    
    def __init__(self):
        # Load from environment or use defaults
        self.max_history_messages = int(os.getenv("JARVIS_MAX_HISTORY_MESSAGES", "8"))
        self.max_memory_snippets = int(os.getenv("JARVIS_MAX_MEMORY_SNIPPETS", "5"))
        self.max_chars_per_snippet = int(os.getenv("JARVIS_MAX_CHARS_PER_SNIPPET", "500"))
        self.max_total_chars = int(os.getenv("JARVIS_MAX_TOTAL_CHARS", "4000"))
    
    def enforce_budget(
        self, 
        history_messages: List[Dict], 
        memory_snippets: List[str]
    ) -> tuple[List[Dict], List[str], Dict[str, int], bool, int]:
        """
        Enforce context budget by trimming if necessary.
        
        Returns:
            (trimmed_history, trimmed_memory, context_counts, budget_exceeded, items_trimmed)
        """
        budget_exceeded = False
        items_trimmed = 0
        
        # Trim history messages
        trimmed_history = history_messages[:self.max_history_messages]
        if len(trimmed_history) < len(history_messages):
            budget_exceeded = True
            items_trimmed += len(history_messages) - len(trimmed_history)
        
        # Trim memory snippets
        trimmed_memory = []
        total_chars = 0
        
        for snippet in memory_snippets[:self.max_memory_snippets]:
            # Truncate individual snippets if too long
            if len(snippet) > self.max_chars_per_snippet:
                snippet = snippet[:self.max_chars_per_snippet] + "..."
                budget_exceeded = True
                items_trimmed += 1
            
            # Check total character budget
            if total_chars + len(snippet) > self.max_total_chars:
                budget_exceeded = True
                break
            
            trimmed_memory.append(snippet)
            total_chars += len(snippet)
        
        if len(trimmed_memory) < len(memory_snippets):
            budget_exceeded = True
            items_trimmed += len(memory_snippets) - len(trimmed_memory)
        
        context_counts = {
            "history_messages": len(trimmed_history),
            "memory_snippets": len(trimmed_memory),
            "total_chars": total_chars
        }
        
        return trimmed_history, trimmed_memory, context_counts, budget_exceeded, items_trimmed


# Global budget instance
_budget = ContextBudget()


def get_budget() -> ContextBudget:
    """Get the global context budget."""
    return _budget


# Model profile definitions for Ollama runtime tuning
MODEL_PROFILES = {
    "fast": {
        "num_ctx": 2048,  # Lower context for speed
        "num_predict": 512,  # Shorter responses
        "temperature": 0.7,  # Balanced creativity
        "top_p": 0.9,  # Focused sampling
        "description": "Fast responses with lower context"
    },
    "balanced": {
        "num_ctx": 4096,  # Standard context
        "num_predict": 1024,  # Standard response length
        "temperature": 0.8,  # Good creativity
        "top_p": 0.95,  # Balanced sampling
        "description": "Balanced performance and quality"
    },
    "quality": {
        "num_ctx": 8192,  # Higher context for complex tasks
        "num_predict": 2048,  # Longer responses
        "temperature": 0.9,  # Higher creativity
        "top_p": 0.98,  # Diverse sampling
        "description": "High quality with more context and tokens"
    }
}


def get_model_profile_params(profile: str) -> Dict[str, Any]:
    """Get Ollama parameters for a model profile."""
    return MODEL_PROFILES.get(profile, MODEL_PROFILES["balanced"]).copy()


def get_available_profiles() -> List[str]:
    """Get list of available model profiles."""
    return list(MODEL_PROFILES.keys())


def validate_profile(profile: str) -> bool:
    """Validate if a profile name is valid."""
    return profile in MODEL_PROFILES


def log_performance_metrics(metrics: PerformanceMetrics) -> None:
    """Log performance metrics to database."""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO performance_metrics (
                    timestamp, user_id, session_id, 
                    memory_retrieval_ms, tool_calls_total_ms, llm_call_ms, total_request_ms,
                    context_items, context_chars, budget_exceeded, items_trimmed,
                    tool_calls
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp,
                metrics.user_id,
                metrics.session_id,
                metrics.memory_retrieval_ms,
                metrics.tool_calls_total_ms,
                metrics.llm_call_ms,
                metrics.total_request_ms,
                json.dumps(metrics.context_items),
                metrics.context_chars,
                1 if metrics.budget_exceeded else 0,
                metrics.items_trimmed,
                json.dumps(metrics.tool_calls)
            ))
            conn.commit()
    except Exception as e:
        # Log error but don't fail the request
        print(f"Failed to log performance metrics: {e}")


def get_recent_performance(user_id: str, session_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Get recent performance metrics for display."""
    try:
        with get_conn() as conn:
            if session_id:
                rows = conn.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE user_id = ? AND session_id = ? 
                    ORDER BY timestamp DESC LIMIT ?
                """, (user_id, session_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM performance_metrics 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC LIMIT ?
                """, (user_id, limit)).fetchall()
            
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Failed to get performance metrics: {e}")
        return []


def format_performance_status(metrics_list: List[Dict[str, Any]], ui_lang: str = "da") -> str:
    """Format performance metrics for display."""
    if not metrics_list:
        return "Ingen performance data fundet." if ui_lang.startswith("da") else "No performance data found."
    
    latest = metrics_list[0]
    
    if ui_lang.startswith("da"):
        status = f"""Performance status (seneste tur):

Timings:
- Hukommelse: {latest.get('memory_retrieval_ms', 0):.1f}ms
- Værktøjer: {latest.get('tool_calls_total_ms', 0):.1f}ms  
- LLM kald: {latest.get('llm_call_ms', 0):.1f}ms
- Total: {latest.get('total_request_ms', 0):.1f}ms

Kontekst:
- Historik beskeder: {latest.get('context_items', {}).get('history_messages', 0)}
- Hukommelse snippets: {latest.get('context_items', {}).get('memory_snippets', 0)}
- Total tegn: {latest.get('context_chars', 0)}

Budget overskredet: {'Ja' if latest.get('budget_exceeded') else 'Nej'}
Elementer trimmet: {latest.get('items_trimmed', 0)}"""
    else:
        status = f"""Performance status (last turn):

Timings:
- Memory: {latest.get('memory_retrieval_ms', 0):.1f}ms
- Tools: {latest.get('tool_calls_total_ms', 0):.1f}ms
- LLM call: {latest.get('llm_call_ms', 0):.1f}ms
- Total: {latest.get('total_request_ms', 0):.1f}ms

Context:
- History messages: {latest.get('context_items', {}).get('history_messages', 0)}
- Memory snippets: {latest.get('context_items', {}).get('memory_snippets', 0)}
- Total chars: {latest.get('context_chars', 0)}

Budget exceeded: {'Yes' if latest.get('budget_exceeded') else 'No'}
Items trimmed: {latest.get('items_trimmed', 0)}"""
    
    # Add tool details if available
    tool_calls = latest.get('tool_calls', [])
    if tool_calls:
        if ui_lang.startswith("da"):
            status += "\n\nVærktøj detaljer:"
            for tool in tool_calls:
                status += f"\n- {tool['name']}: {tool['latency_ms']:.1f}ms ({'succes' if tool['success'] else 'fejl'})"
        else:
            status += "\n\nTool details:"
            for tool in tool_calls:
                status += f"\n- {tool['name']}: {tool['latency_ms']:.1f}ms ({'success' if tool['success'] else 'error'})"
    
    return status