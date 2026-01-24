

# Jarvis Agent

Jarvis Agent is a local-first FastAPI service with a lightweight web UI (`/app`) that wraps LLM chat, tools, EventBus/EventStore streaming, and an Admin dashboard. It runs on SQLite with no paid services required.

## Features
- Chat UI with streaming and session history
- Admin dashboard for tickets, logs, users, and SettingsStore
- Tools: weather/news/web search, system/process info, files/notes, etc.
- EventBus/EventStore pipeline (`/v1/events`, `/v1/events/stream`) for live updates
- DB-backed SettingsStore with public/admin scopes
- Local SQLite storage (configurable path)

## Quickstart (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn jarvis.server:app --reload --host 0.0.0.0 --port 8000
```
Open: http://127.0.0.1:8000/app

Run tests (recommended):
```bash
bash -lc 'PYTHONPATH=src pytest -q'
```

## Configuration
- **Environment variables:**
  - `JARVIS_DB_PATH` — SQLite DB path (default: ./data/jarvis.db)
  - `JARVIS_DEVKEY` — dev key for bearer access (default: devkey; change for production)
  - `JARVIS_TEST_MODE` — `1` to disable watchers/background threads in tests
  - `JARVIS_EVENT_BACKLOG` — in-memory event backlog (default 1000)
  - Cookie flags: `JARVIS_COOKIE_NAME`, `JARVIS_COOKIE_SECURE`, `JARVIS_COOKIE_SAMESITE`, `JARVIS_COOKIE_TTL_SECONDS`
- **SettingsStore** (SQLite `settings` table):
  - Scopes: `public` (exposed via `/settings/public`), `admin` (admin-only)
  - Admin endpoints: `GET /admin/settings`, `PUT /admin/settings` (auth required)
- **Auth:**
  - Demo/default user auto-created in dev
  - Admin: set `is_admin=1` on a user (DB or Admin UI)
  - Session cookie `jarvis_token` stays valid; admin 401 does **not** clear it

## Troubleshooting
- 401 on Admin endpoints: ensure user is admin; session remains valid.
- “jarvis_token missing”: confirm login and cookie acceptance (SameSite=Lax).
- EventBus/EventStore: `/v1/events/stream` uses `max_ms` for deterministic termination; clients back off on errors.
- Test hangs: set `JARVIS_TEST_MODE=1` and run `bash -lc 'PYTHONPATH=src pytest -q'`, or wrap with:
  ```bash
  timeout 600s bash -lc 'PYTHONPATH=src pytest -q'
  ```
- DB locked: avoid multiple servers on same DB or set `JARVIS_DB_PATH` to a fresh temp path for tests.

## Documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API.md](docs/API.md)
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

## Troubleshooting
- 401 on admin endpoints: ensure user is admin; session remains valid.
- “jarvis_token missing”: confirm login and cookie acceptance (SameSite=Lax).
- SSE/events: `/v1/events/stream` uses `max_ms` for deterministic termination; clients back off on errors.
- Test hangs: set `JARVIS_TEST_MODE=1` and run `PYTHONPATH=src pytest -q`, or wrap with:
  ```bash
  timeout 600s bash -lc 'PYTHONPATH=src pytest -q'
  ```
- DB locked: avoid multiple servers on the same DB or set `JARVIS_DB_PATH` to a temp path for tests.

## Documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API.md](docs/API.md)
- [docs/OPERATIONS.md](docs/OPERATIONS.md)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- [docs/UI_REFACTOR_PLAN.md](docs/UI_REFACTOR_PLAN.md)

## UI development

- Main entrypoint: `ui/index.html` (all UI: chat, admin, account, etc.)
- Static assets: `ui/static/app.js`, `index-app.js`, `app.css`, `app-fix.css`, `api.js`, `auth.js`, `authStore.js`, `admin.js`
- All base CSS variables and typography are in `app.css` (see comments in `styles.css`)
- No build step: vanilla HTML/CSS/JS. Serve via `uvicorn jarvis.server:app` and open `/app` (or `/index.html`)
- Minimal JS state: `index-app.js` fetches `/me` (or `/auth/me`) and tracks `is_admin` for UI logic
- Auth: `jarvis_token` cookie; admin features require `is_admin`. 401 on admin routes does **not** clear session.

## Security
- Do not use default dev keys in production (`JARVIS_DEVKEY`).
- Always use HTTPS in production and set `JARVIS_COOKIE_SECURE=1`.
- No secrets or unsafe defaults are exposed in public endpoints.
