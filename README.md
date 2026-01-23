
# Jarvis — Lokal AI-assistent

Jarvis er en lokal AI-assistent bygget på FastAPI + Ollama med værktøjer, hukommelse, billedanalyse og et web-UI.

## 🚀 Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m jarvis.server
```

Åbn: http://127.0.0.1:8000/app

## Demo-bruger
- Brugernavn: demo
- Email: demo@example.com
- Password: demo

## Tests

Kør alle tests:

```bash
PYTHONPATH=src pytest -q
```

Med timeout (anbefalet for CI eller lange tests):

```bash
timeout 600s bash -lc 'PYTHONPATH=src pytest -q'
# eller
timeout 600s env PYTHONPATH=src pytest -q
```

## Konfiguration

Se [docs/configuration.md](docs/configuration.md) for alle miljøvariabler og typiske værdier.

## Troubleshooting

Se [docs/troubleshooting.md](docs/troubleshooting.md) for fejlsøgning af test-hæng, 401-fejl, cookie-problemer og streaming.

## Arkitektur

Se [docs/architecture.md](docs/architecture.md) for et hurtigt overblik over systemet.

## Dokumentation

- [docs/running.md](docs/running.md) — Sådan starter du projektet
- [docs/testing.md](docs/testing.md) — Test og CI
- [docs/configuration.md](docs/configuration.md) — Miljøvariabler
- [docs/troubleshooting.md](docs/troubleshooting.md) — Fejlsøgning
- [docs/architecture.md](docs/architecture.md) — Arkitektur
