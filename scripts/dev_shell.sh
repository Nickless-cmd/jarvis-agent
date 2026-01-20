#!/usr/bin/env bash
set -e
cd /home/bs/jarvis-agent
source .venv/bin/activate
set -a
source .env
set +a
exec bash
