#!/usr/bin/env bash
# scripts/stop.sh
# ─────────────────────────────────────────────────────────────────────────────
# Gracefully stop the Headless Bob Demo Streamlit application.
#
# Usage: ./scripts/stop.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/.app.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "ℹ️  No PID file found. App may not be running."
  exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
  echo "🛑 Stopping Headless Bob Demo (PID $PID)…"
  kill -TERM "$PID"

  # Wait up to 10 seconds for the process to exit cleanly
  TIMEOUT=10
  ELAPSED=0
  while kill -0 "$PID" 2>/dev/null && [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
  done

  if kill -0 "$PID" 2>/dev/null; then
    echo "⚠️  Process did not stop; sending SIGKILL…"
    kill -KILL "$PID" || true
  fi

  rm -f "$PID_FILE"
  echo "✅ Stopped."
else
  echo "ℹ️  Process $PID is not running. Cleaning up stale PID file."
  rm -f "$PID_FILE"
fi
