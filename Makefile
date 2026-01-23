.PHONY: dev test

dev:
	PYTHONPATH=src uvicorn jarvis.server:app --reload --host 127.0.0.1 --port 8000

test:
	PYTHONPATH=src pytest -q