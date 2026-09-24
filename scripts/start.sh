#!/usr/bin/env bash
# scripts/start.sh
# ─────────────────────────────────────────────────────────────────────────────
# Launch the Headless Bob Demo Streamlit application in detached mode.
# The app URL is printed to the console.
#
# Usage: ./scripts/start.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Resolve project root (one level above this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/.app.pid"
LOG_FILE="$PROJECT_ROOT/.app.log"
APP_PORT=8501

cd "$PROJECT_ROOT"

# ── Check for an already-running instance ────────────────────────────────────
if [ -f "$PID_FILE" ]; then
  EXISTING_PID=$(cat "$PID_FILE")
  if kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "⚠️  App is already running (PID $EXISTING_PID)"
    echo "   Use ./scripts/stop.sh to stop it first."
    exit 1
  else
    # Stale PID file — clean it up
    rm -f "$PID_FILE"
  fi
fi

# ── Activate virtual environment ──────────────────────────────────────────────
if [ -d "$PROJECT_ROOT/.venv" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate"
else
  echo "⚠️  No .venv found. Creating one now…"
  python3 -m venv "$PROJECT_ROOT/.venv"
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate"
  pip install -q -r "$PROJECT_ROOT/requirements.txt"
fi

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
  # Export only non-comment, non-blank lines
  set -o allexport
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +o allexport
fi

# ── Start Streamlit in the background ────────────────────────────────────────
nohup streamlit run \
  "$PROJECT_ROOT/src/app.py" \
  --server.port "$APP_PORT" \
  --server.headless true \
  --browser.gatherUsageStats false \
  > "$LOG_FILE" 2>&1 &

APP_PID=$!
echo "$APP_PID" > "$PID_FILE"

# Give Streamlit a moment to start
sleep 2

# Verify it started successfully
if kill -0 "$APP_PID" 2>/dev/null; then
  echo "✅ Headless Bob Demo is running"
  echo "   PID  : $APP_PID"
  echo "   URL  : http://localhost:${APP_PORT}"
  echo "   Logs : $LOG_FILE"
  echo ""
  echo "   Stop with: ./scripts/stop.sh"
else
  echo "❌ Failed to start. Check logs:"
  cat "$LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
