# Running Jarvis

## Quickstart (Linux/Ubuntu)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m jarvis.server
```

Open the UI at: http://127.0.0.1:8000/app

## Development mode (hot reload)

```bash
JARVIS_PROJECT_ROOT=$(pwd) PYTHONPATH=src uvicorn jarvis.server:app --reload --host 127.0.0.1 --port 8000
```

## Demo user
- Username: demo
- Email: demo@example.com
- Password: demo
