# Troubleshooting

## Pytest hangs
- Use: `timeout 600s bash -lc 'PYTHONPATH=src pytest -q'`
- Check for stuck processes or locked files in data/ or memory/.
- Some tests (event bus, memory) may be slow if DB is not clean.

## 401 on /admin/*
- Ensure you are logged in as admin (not demo).
- Check that your browser sends the `jarvis_token` cookie and (if needed) the devkey header.
- Demo users cannot access /admin/* endpoints.

## Immediate logout after login
- Check cookie settings: SameSite, Secure, domain.
- Use browser devtools to verify the `jarvis_token` cookie is set and sent.
- If running on localhost, set `JARVIS_COOKIE_SECURE=0` and `JARVIS_COOKIE_SAMESITE=Lax`.

## SSE stream hangs
- Check if query params like `max_ms` are set (controls stream duration).
- If stream hangs, try restarting the server and clearing browser cache.
- Check for network errors in browser devtools.
