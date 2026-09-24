# Headless Bob Demo — Project Artifact

## Summary

**Project:** Headless Bob Demo
**Purpose:** Demonstrate IBM Bob Shell as a headless REST service (Headless Bob)
**Status:** Complete — all bug fixes applied and documentation updated
**Language:** Python 3.11+
**UI:** Streamlit

---

## Delivered Files

| File | Role |
|---|---|
| `src/app.py` | Streamlit UI — main entry point |
| `src/headless_bob_client.py` | REST + SSE client for the Headless Bob API |
| `tests/test_headless_bob_client.py` | 32 offline unit tests (no live service needed) |
| `Docs/Quickstart.md` | Step-by-step setup guide |
| `Docs/Architecture.md` | Architecture diagrams and data-flow documentation |
| `scripts/start.sh` | Launch app in detached mode, print URL |
| `scripts/stop.sh` | Graceful shutdown |
| `scripts/cleanup.sh` | Remove .venv, __pycache__, output/ contents |
| `.env.example` | Environment variable template |
| `requirements.txt` | Python dependencies |
| `README.md` | Full project documentation with licence |
| `.gitignore` | Git exclusion rules per AGENTS.md conventions |

---

## Key Integration Points

1. **Thread management** — `POST /api/v1/threads` creates isolated Bob workspaces
2. **Prompt dispatch** — `POST /api/v1/threads/{id}/messages` enqueues a `bob run`.
   The message body only accepts `{"content": <string>}` — a `mode` field is not
   accepted (`additionalProperties: false`). The selected mode is prepended to the
   prompt text as `[Mode: <name>]` when a non-default mode is chosen.
3. **Run ID extraction** — `run_id` is at `data["run"]["run_id"]` in the response,
   not at the top level.
4. **SSE streaming** — `GET /api/v1/runs/{id}/events` delivers live output via events
   typed `run.created` → `run.in-progress` → `message.part` (×N) → `message.completed`
   → `run.completed` (or `run.failed`).
5. **Workspace I/O** — `GET /api/v1/threads/{id}/files` exposes files Bob created

---

## Bug Fixes Applied

| # | Bug | Root cause | Fix location |
|---|---|---|---|
| 1 | HTTP 400 Bad Request on every message | `send_message()` included `"mode"` in the JSON body; API rejects extra fields | `src/headless_bob_client.py` `send_message()` |
| 2 | Run ID was always empty string | Code read `data["run_id"]` (top-level); actual path is `data["run"]["run_id"]` | `src/headless_bob_client.py` `send_message()` |
| 3 | SSE stream never produced output | Code matched event types `result`, `message` (plain); actual types are `run.completed`, `message.part`, `message.completed` | `src/app.py` SSE event loop |

---

## AGENTS.md Compliance Checklist

- [x] Python + Streamlit UI (no cloud dependency)
- [x] Virtual environment with requirements.txt
- [x] .env.example (no hard-coded credentials)
- [x] Unit tests for all client functions (32 tests, 31 pass + 1 skipped when offline)
- [x] README.md with Mermaid architecture diagram and Building Blocks rationale
- [x] Docs/Quickstart.md
- [x] Docs/Architecture.md with Mermaid diagrams
- [x] scripts/start.sh (detached, prints URL)
- [x] scripts/stop.sh (graceful)
- [x] scripts/cleanup.sh (removes .venv, __pycache__, output contents)
- [x] .gitignore with all AGENTS.md required exclusions
- [x] input/ and output/ folders with .gitkeep
- [x] Apache 2.0 licence in README.md
- [x] No port 5000 (uses 8501)
- [x] English throughout
