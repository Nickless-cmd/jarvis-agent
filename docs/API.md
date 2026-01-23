# API Overview

All routes are served from the FastAPI app in `src/jarvis/server.py`.

## Public/status
- `GET /status` — basic health/status.
- `GET /settings/public` — public UI settings (lang/theme/banner/footer). No secrets.
- `GET /v1/brand` — branding labels.

## Chat
- `POST /v1/chat/completions` — chat endpoint. Body: OpenAI-like {model, messages, stream?}. Returns assistant reply or streaming SSE.

## Events
- `GET /v1/events` — snapshot, non-blocking. Query: `since_id` optional. Returns {events, last_id}.
- `GET /v1/events/stream` — SSE stream. Query: `since_id`, `max_ms`, `max_events`, optional filters. Deterministic termination under `max_ms`/`max_events`.

## Files/Notes (user)
- `GET /files`, `POST /files` (upload), `DELETE /files/{id}`, `GET /files/{id}` (download via token).
- `GET /notes`, `POST /notes`, `DELETE /notes/{id}`, reminder helpers.

## Admin
- `GET /admin/settings` — list settings (admin only).
- `PUT /admin/settings` — update setting {key, value, scope?} (public/admin scopes).
- `GET /admin/tickets`, `GET /admin/tickets/{id}`, `PATCH /admin/tickets/{id}`, `POST /admin/tickets/{id}/reply`.
- `GET /admin/logs` (list), `GET /admin/logs/{name}` (content), `DELETE /admin/logs/{name}`.
- `GET /admin/users`/`PATCH`/`DELETE` (standard user admin).

## Curl examples
```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Cookie: jarvis_token=...your token..." \\
  -d '{ "model": "local", "messages":[{"role":"user","content":"Hej Jarvis"}] }'

curl "http://127.0.0.1:8000/v1/events?since_id=0" -H "Cookie: jarvis_token=..."

curl -X PUT http://127.0.0.1:8000/admin/settings \\
  -H "Content-Type: application/json" \\
  -H "Cookie: jarvis_token=...admin token..." \\
  -d '{ "key": "ui_default_lang", "value": "da", "scope": "public" }'
```
