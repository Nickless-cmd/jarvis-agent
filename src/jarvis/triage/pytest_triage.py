"""Pytest failure triage utilities."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from jarvis.code_rag.search import search_code

MAX_BODY = 2000
MAX_SUGGESTIONS = 3


def _truncate(text: str, limit: int = MAX_BODY) -> str:
    return (text or "")[:limit]


def _extract_nodeid(output: str) -> str | None:
    m = re.search(r"^([\\w./-]+::[^\\s]+)\\s+(FAILED|ERROR)", output, flags=re.MULTILINE)
    return m.group(1) if m else None


def _extract_trace_excerpt(output: str) -> str:
    lines = output.splitlines()
    excerpt: List[str] = []
    for line in lines:
        if line.strip().startswith("E   "):
            excerpt.append(line.strip())
        if len(excerpt) >= 6:
            break
    if not excerpt:
        excerpt = lines[:6]
    return "\\n".join(excerpt)


def triage_pytest_output(output: str, ui_lang: str = "da") -> Dict[str, Any]:
    """
    Produce a triage summary for pytest output with extracted query terms.
    Returns dict with title, body, query_terms.
    """
    lang = (ui_lang or "da").lower()
    is_en = lang.startswith("en")
    
    # Extract failing tests
    failing_tests = []
    for line in output.splitlines():
        if "::" in line and ("FAILED" in line or "ERROR" in line):
            parts = line.split("::", 1)
            if len(parts) > 1:
                test_name = parts[1].split()[0]
                failing_tests.append(test_name)
    
    # Extract query terms
    query_terms = set()
    
    # Python file paths
    for match in re.finditer(r"(\w+/\w+.*?\.py)", output):
        query_terms.add(match.group(1))
    
    # Function/class names from def or in lines
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("def ") or " in " in line:
            # Extract after def or before/after in
            if line.startswith("def "):
                name = line.split()[1].split("(")[0]
                query_terms.add(name)
            elif " in " in line:
                parts = line.split(" in ")
                for part in parts[1:]:
                    name = part.split()[0].strip("()[]")
                    if name:
                        query_terms.add(name)
    
    # Exception types
    exceptions = ["ValueError", "KeyError", "AssertionError", "TypeError", "AttributeError", "IndexError", "NameError"]
    for exc in exceptions:
        if exc in output:
            query_terms.add(exc)
    
    query_terms = list(query_terms)[:5]  # Limit to 5
    
    # Build title and body
    num_failed = len(failing_tests)
    if is_en:
        title = f"Tests failed ({num_failed})" if num_failed > 0 else "Tests passed"
        body = f"Failed tests: {', '.join(failing_tests[:3])}" if failing_tests else "All tests passed"
    else:
        title = f"Tests fejlede ({num_failed})" if num_failed > 0 else "Tests bestået"
        body = f"Fejlede tests: {', '.join(failing_tests[:3])}" if failing_tests else "Alle tests bestået"
    
    return {
        "title": title,
        "body": body,
        "query_terms": query_terms,
    }
