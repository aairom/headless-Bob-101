#!/usr/bin/env bash
# scripts/cleanup.sh
# ─────────────────────────────────────────────────────────────────────────────
# Remove generated artefacts from the project:
#   - Python virtual environment (.venv)
#   - Python byte-code cache (__pycache__, .pyc files)
#   - Contents of the output/ folder (keeps the directory itself)
#
# Does NOT delete source code, documentation, or input files.
#
# Usage: ./scripts/cleanup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🧹 Cleaning up project artefacts…"

# ── Stop the app if running ───────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.app.pid" ]; then
  echo "   Stopping running application first…"
  "$SCRIPT_DIR/stop.sh" || true
fi

# ── Remove virtual environment ────────────────────────────────────────────────
if [ -d "$PROJECT_ROOT/.venv" ]; then
  echo "   Removing .venv…"
  rm -rf "$PROJECT_ROOT/.venv"
fi

# ── Remove Python caches ──────────────────────────────────────────────────────
echo "   Removing __pycache__ directories…"
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "   Removing .pyc / .pyo files…"
find "$PROJECT_ROOT" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true

echo "   Removing pytest cache…"
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

echo "   Removing coverage artifacts…"
rm -f "$PROJECT_ROOT/.coverage"
rm -rf "$PROJECT_ROOT/htmlcov"

# ── Clear output/ folder contents ────────────────────────────────────────────
OUTPUT_DIR="$PROJECT_ROOT/output"
if [ -d "$OUTPUT_DIR" ]; then
  echo "   Clearing output/ folder contents…"
  find "$OUTPUT_DIR" -mindepth 1 ! -name ".gitkeep" -delete 2>/dev/null || true
fi

# ── Remove log file ───────────────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.app.log" ]; then
  echo "   Removing .app.log…"
  rm -f "$PROJECT_ROOT/.app.log"
fi

echo ""
echo "✅ Cleanup complete."
echo "   Re-run setup with:"
echo "   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
