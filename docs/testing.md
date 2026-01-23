# Testing Jarvis

## Standard test run

```bash
PYTHONPATH=src pytest -q
```

## With timeout (recommended for CI or long tests)

```bash
timeout 600s bash -lc 'PYTHONPATH=src pytest -q'
# or
timeout 600s env PYTHONPATH=src pytest -q
```

## Troubleshooting test hangs
- If pytest hangs, use the timeout command above.
- Some tests (e.g. event bus, memory) may take longer or hang if DB/config is not clean.
- Check for leftover processes or locked files in data/ or memory/.
