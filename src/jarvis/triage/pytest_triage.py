"""Pytest failure triage utilities."""

from __future__ import annotations

import re
from typing import Any, Dict, List

MAX_BODY = 2000
MAX_SUGGESTIONS = 3


def _truncate(text: str, limit: int = MAX_BODY) -> str:
    return (text or "")[:limit]


def parse_pytest_output(output: str) -> Dict[str, Any]:
    """Parse pytest output into a structured summary."""
    failing_tests: List[str] = []
    file_paths: List[str] = []
    line_numbers: List[int] = []
    trace_snippets: List[str] = []
    error_type: str | None = None
    error_message: str | None = None

    for line in output.splitlines():
        line_stripped = line.strip()
        # Nodeids like tests/test_example.py::test_func FAILED
        node_match = re.search(r"([A-Za-z0-9_./-]+::[A-Za-z0-9_./-]+)", line)
        if node_match and ("FAILED" in line or "ERROR" in line or "FAILED" in line_stripped.upper() or "ERROR" in line_stripped.upper()):
            failing_tests.append(node_match.group(1))
        # Alt format: FAILED test_example.py::test_func - ...
        alt_match = re.search(r"FAILED\s+([A-Za-z0-9_./-]+::[A-Za-z0-9_./-]+)", line)
        if alt_match:
            failing_tests.append(alt_match.group(1))
        # File paths and line numbers
        for match in re.finditer(r"([A-Za-z0-9_./-]+\.py)(?::(\d+))?", line):
            file_paths.append(match.group(1))
            if match.group(2):
                try:
                    line_numbers.append(int(match.group(2)))
                except ValueError:
                    pass
        # Trace lines
        if line_stripped.startswith("E   "):
            trace_snippets.append(line_stripped)
        elif ".py" in line_stripped and " in " in line_stripped:
            # Traceback line like "file.py:123: in func"
            trace_snippets.append(line_stripped)
        # Exception extraction
        if error_type is None:
            exc_match = re.search(
                r"E\s+(?P<etype>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))(?::\s*(?P<msg>.+))?",
                line_stripped,
            )
            if exc_match:
                error_type = exc_match.group("etype")
                error_message = exc_match.group("msg")
        if error_type is None:
            exc_match = re.search(
                r"(SyntaxError|IndentationError)(?::\s*(.+))?",
                line_stripped,
            )
            if exc_match:
                error_type = exc_match.group(1)
                error_message = exc_match.group(2)

    # Deduplicate and trim
    failing_tests = list(dict.fromkeys(failing_tests))
    file_paths = list(dict.fromkeys(file_paths))
    trace_snippets = trace_snippets[:6] if trace_snippets else output.splitlines()[:6]

    return {
        "failing_tests": failing_tests,
        "file_paths": file_paths,
        "line_numbers": line_numbers,
        "error_type": error_type,
        "error_message": _truncate(error_message, 300) if error_message else None,
        "trace_snippets": trace_snippets,
    }


def suggest_next_queries(parsed: Dict[str, Any]) -> List[str]:
    """Derive deterministic search queries from parsed pytest output."""
    terms: List[str] = []
    terms.extend(parsed.get("failing_tests") or [])
    terms.extend(parsed.get("file_paths") or [])
    if parsed.get("error_type"):
        terms.append(parsed["error_type"])
    if parsed.get("error_message"):
        words = (parsed["error_message"] or "").split()
        terms.extend(words[:3])
    for snippet in parsed.get("trace_snippets") or []:
        match = re.search(r"in\s+([A-Za-z_][A-Za-z0-9_]*)", snippet)
        if match:
            terms.append(match.group(1))
    cleaned = []
    seen = set()
    for t in terms:
        t = t.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
        if len(cleaned) >= 8:
            break
    return cleaned


def triage_pytest_output(output: str, ui_lang: str = "da") -> Dict[str, Any]:
    """
    Produce a triage summary for pytest output with extracted query terms.
    Returns dict with title, body, query_terms, summary.
    """
    lang = (ui_lang or "da").lower()
    is_en = lang.startswith("en")

    parsed = parse_pytest_output(output)
    failing_tests = parsed.get("failing_tests") or []
    num_failed = len(failing_tests)

    if num_failed > 0:
        title = f"Tests failed ({num_failed})" if is_en else f"Tests fejlede ({num_failed})"
        prefix = "Failed tests: " if is_en else "Fejlede tests: "
        body = prefix + ", ".join(failing_tests[:5])
    else:
        title = "Tests passed" if is_en else "Tests bestået"
        body = "All tests passed" if is_en else "Alle tests bestået"

    query_terms = suggest_next_queries(parsed)

    summary = body
    if parsed.get("error_type"):
        summary += f" | {parsed['error_type']}"

    return {
        "title": title,
        "body": body,
        "query_terms": query_terms,
        "summary": summary,
        "parsed": parsed,
    }
