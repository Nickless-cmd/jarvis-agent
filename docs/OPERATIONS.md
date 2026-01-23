# Operations

## Run / Deploy
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn jarvis.server:app --host 0.0.0.0 --port 8000
```

## Configuration (env)
- `JARVIS_DB_PATH` — SQLite path (default: ./data/jarvis.db)
- `JARVIS_DEVKEY` — dev bearer key (default: devkey)
- `JARVIS_TEST_MODE=1` — disables watchers/background threads (use in tests/CI)
- `JARVIS_EVENT_BACKLOG` — event store backlog (default 1000)
- Cookie flags: `JARVIS_COOKIE_NAME`, `JARVIS_COOKIE_SECURE`, `JARVIS_COOKIE_SAMESITE`, `JARVIS_COOKIE_TTL_SECONDS`

## Settings store
- Stored in `settings` table (key, value_json, scope, updated_at).
- Scopes: `public` (exposed at `/settings/public`), `admin` (admin-only).
- Admin API: `GET /admin/settings`, `PUT /admin/settings` to upsert {key,value,scope}.

## Logs
- API logs: `data/logs` (TimedRotatingFileHandler, size bounded).
- Admin can read via `/admin/logs` endpoints.

## Security notes
- Use HTTPS in production; set `JARVIS_COOKIE_SECURE=1`.
- Set a strong `JARVIS_DEVKEY` or disable dev bearer in prod.
- Admin endpoints require `is_admin`; 401/403 on admin routes do not invalidate user sessions.

## Health
- `GET /status` returns `{ok, online, version}`.
- Events: `GET /v1/events` snapshot; `GET /v1/events/stream` SSE with `max_ms`/`max_events`.
