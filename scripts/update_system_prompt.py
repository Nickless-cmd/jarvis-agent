import sqlite3
from pathlib import Path


def extract_prompt() -> str:
    path = Path(__file__).resolve().parents[1] / "src" / "jarvis" / "personality.py"
    text = path.read_text(encoding="utf-8")
    marker = "SYSTEM_PROMPT"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("SYSTEM_PROMPT not found")
    start = text.find('"""', idx)
    end = text.find('"""', start + 3)
    if start == -1 or end == -1:
        raise SystemExit("SYSTEM_PROMPT block not found")
    return text[start + 3 : end].strip()


def main() -> None:
    db = Path(__file__).resolve().parents[1] / "data" / "jarvis.db"
    prompt = extract_prompt()
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("system_prompt", prompt),
        )
        conn.commit()
    print("system_prompt updated")


if __name__ == "__main__":
    main()
