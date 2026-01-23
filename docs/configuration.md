# Configuration

## Environment Variables

| Variable                    | Default                | Description                                  | Typical values         |
|-----------------------------|------------------------|----------------------------------------------|-----------------------|
| JARVIS_TEST_MODE            | 0                      | Enable test mode (faster, less strict)       | 0, 1                  |
| JARVIS_DB_PATH              | ./data/jarvis.db       | Path to SQLite DB                            | /tmp/jarvis.db, ...   |
| JARVIS_TOOL_TIMEOUT_DEFAULT | 30                     | Default tool timeout (seconds)               | 10, 30, 60            |
| JARVIS_TOOL_RETRIES         | 2                      | Tool retry attempts                          | 0, 1, 2, 3            |
| JARVIS_EVENT_BACKLOG        | 1000                   | Max events in memory/event bus               | 100, 1000, 10000      |
| JARVIS_EVENT_STORE_PATH     | ./data/events.db       | Path to event store DB                       | /tmp/events.db, ...   |
| JARVIS_DEVKEY               | (none)                 | Dev API key for admin endpoints              | any string            |
| JARVIS_COOKIE_SECURE        | 0                      | Set cookies as Secure (HTTPS only)           | 0, 1                  |
| JARVIS_COOKIE_SAMESITE      | Lax                    | Cookie SameSite policy                       | Lax, Strict, None     |

- All variables can be set in your shell or in a .env file.
- For dev/test, use JARVIS_TEST_MODE=1 and a temp DB path.
- For production, set secure cookie options and a persistent DB path.
