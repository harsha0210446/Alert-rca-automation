#!/usr/bin/env bash
# Start the full automation server (webhook → auto RCA → Google Chat)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d ".venv" ]; then
  echo "Run setup first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "config.env" ]; then
  echo "Copy config.env.example to config.env and fill in values"
  exit 1
fi

# Check required config
source /dev/null 2>&1 || true
if ! grep -q "ANTHROPIC_API_KEY=.\+" config.env 2>/dev/null && ! grep -q "OPENAI_API_KEY=.\+" config.env 2>/dev/null; then
  echo "⚠ Set ANTHROPIC_API_KEY or OPENAI_API_KEY in config.env"
fi

echo "Starting automation server..."
echo "Expose with ngrok if running locally: ngrok http 8080"
exec .venv/bin/python scripts/webhook_server.py
