# Jarvis — Lokal AI-assistent

Jarvis er en lokal AI‑assistent bygget på FastAPI + Ollama med værktøjer, hukommelse, billedanalyse og et web‑UI.

## 🚀 **Nyeste Features**
- **Billedanalyse** med avanceret hallucination-beskyttelse
- **Vision-modeller** (moondream:1.8b, llava:7b, llava:13b)
- **Hallucination-detektion** med sprog-filtrering og sikkerhedstjek
- **Debug-logging** for billedanalyse (`JARVIS_DEBUG_IMAGE=1`)

## Hurtig start
```bash
uvicorn jarvis.server:app --host 127.0.0.1 --port 8000
```

Åbn: `http://127.0.0.1:8000/login`

## Demo‑bruger
- Brugernavn: `demo`
- Email: `demo@example.com`
- Password: `demo`

## Dokumentation
Se `docs/README.md` for funktioner, kommandoer og UI‑ruter.

## Database (skrivbar)
Hvis du vil bruge en anden DB‑placering:
```
JARVIS_DB_PATH=/tmp/jarvis.db
```# jarvis-agent
