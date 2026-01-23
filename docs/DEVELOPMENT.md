# Development

## Layout
- `src/jarvis/server.py` — FastAPI app, routes, SSE.
- `src/jarvis/agent.py` + `agent_core/` + `agent_skills/` — chat orchestration and skills.
- `src/jarvis/tools.py` — tool implementations; `tool_registry` wraps them.
- `src/jarvis/events.py` / `event_store.py` — event bus + store.
- `src/jarvis/settings_store.py` — DB-backed settings.
- `ui/` — vanilla HTML/CSS/JS for /app and /admin.

## Testing
```bash
PYTHONPATH=src pytest -q
# With timeout (recommended for CI):
timeout 600s bash -lc 'PYTHONPATH=src pytest -q'
```

## Coding guidelines
- Keep auth/session stable: admin 401 must not clear session.
- Use runtime config (jarvis.config) instead of import-time env checks.
- Event endpoints must be non-blocking (/v1/events) and SSE deterministic (/v1/events/stream with max_ms).
- Prefer SQLite-friendly changes (no heavy migrations).

## Common commands
- Run dev server: `PYTHONPATH=src uvicorn jarvis.server:app --reload --host 0.0.0.0 --port 8000`
- Lint/format: (none enforced, keep diff small and consistent)

## Troubleshooting for devs
- DB locks: use a temp `JARVIS_DB_PATH` when running multiple test processes.
- SSE flakiness in browser: check Network tab; stream should include `max_ms` cadence, not multiple parallel calls.
- Admin UI 401: confirm `is_admin` on user; session cookie remains valid otherwise.
