# Architecture

## Overview
- **server.py**: FastAPI app, routing, auth, SSE/events, static file mounting.
- **agent.py + agent_core/**: Chat orchestration, intent routing, state services.
- **agent_skills/**: CV, story, notes/files, process/admin/history, code, etc.
- **tools.py**: Weather/news/web/system/process tools (wrapped by tool registry).
- **memory.py / session_store.py**: Session state, message storage, FAISS memory.
- **events.py / event_store.py**: In-process event bus and bounded store, exposed via `/v1/events` and `/v1/events/stream`.
- **settings_store.py**: SQLite-backed settings with scope (public/admin).
- **ui/**: Vanilla HTML/CSS/JS for /app and /admin (no frameworks).

## Data storage
- SQLite (configurable path via `JARVIS_DB_PATH`).
- Tables: users, sessions/messages, settings, tickets, notes, files, events, tool audit, performance metrics.

## Auth
- Cookie `jarvis_token` (configurable name).
- Devkey bearer for admin/dev if enabled.
- Admin endpoints require `is_admin`.

## Events
- Publish/subscribe in-process; store keeps bounded backlog.
- `/v1/events` snapshot (non-blocking), `/v1/events/stream` SSE with `max_ms`/`max_events`.

## Settings
- settings_store with scopes:
  - `public` exposed via `/settings/public`
  - `admin` for admin-only
- Admin API to update settings.
