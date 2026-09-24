"""
headless_bob_client.py
======================
Low-level REST client for the **Headless Bob** service
(https://github.com/ibm-self-serve-assets/building-blocks/tree/main/ai/ai-engineering/headless-bob).

Headless Bob exposes IBM Bob Shell as a persistent HTTP service with:
  - Thread-based conversation lifecycle (create / list / delete threads)
  - Asynchronous run execution per thread message
  - Server-Sent Events (SSE) streaming for live output
  - A supplementary Agent Communication Protocol (ACP) interface

This module wraps the REST API (`/api/v1/*`) only. All credentials are read
from environment variables — never hard-coded.

Environment variables required:
  HEADLESS_BOB_URL   Base URL of the running Headless Bob service
                     (e.g. http://127.0.0.1:8000)
  HEADLESS_BOB_TOKEN Bearer token for the service (matches AUTH_TOKENS in .env)
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _base_url() -> str:
    """Return the Headless Bob service base URL from the environment."""
    url = os.environ.get("HEADLESS_BOB_URL", "http://127.0.0.1:8000")
    return url.rstrip("/")


def _auth_header() -> dict:
    """Return the Authorization header dict, reading the token from env."""
    token = os.environ.get("HEADLESS_BOB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "HEADLESS_BOB_TOKEN environment variable is not set. "
            "Copy .env.example to .env and fill in the token."
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Thread:
    """Represents a Headless Bob conversation thread."""
    id: str
    title: str
    created_at: str = ""
    archived: bool = False
    message_count: int = 0


@dataclass
class Run:
    """Represents a Bob Shell execution run."""
    run_id: str
    status: str           # created | in-progress | completed | failed | cancelled
    thread_id: str = ""
    last_message: str = ""
    duration_ms: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    error: str = ""
    events_url: str = ""


@dataclass
class ServerCapabilities:
    """Server capability manifest returned by GET /api/v1/capabilities."""
    version: str = ""
    bob_version: str = ""
    max_concurrent: int = 0
    max_queued: int = 0
    run_timeout_ms: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class WorkspaceFile:
    """A file generated inside a thread's workspace."""
    path: str
    size: int = 0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """
    Perform a JSON request to the Headless Bob REST API.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE).
        path:   API path starting with '/'.
        body:   Optional JSON-serialisable request body.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        urllib.error.HTTPError: On non-2xx responses.
        EnvironmentError:       If HEADLESS_BOB_TOKEN is not set.
    """
    url = _base_url() + path
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(_auth_header())

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    logger.debug("%s %s", method, url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        logger.error("HTTP %s from %s: %s", exc.code, url, body_text)
        raise


def stream_events(events_url: str) -> Generator[dict, None, None]:
    """
    Consume a Server-Sent Events (SSE) stream from Headless Bob.

    Yields parsed event dicts. Handles both relative paths and absolute URLs.
    Each SSE frame contains one JSON object on a ``data:`` line.

    The Headless Bob service emits these event types (``type`` field):
      - ``run.created``       — run has been accepted and queued
      - ``run.in-progress``   — Bob Shell subprocess has started
      - ``message.created``   — assistant message object initialised (empty)
      - ``message.part``      — incremental content delta; read ``part.content``
      - ``message.completed`` — full assembled message; read ``message.parts``
      - ``run.completed``     — run finished successfully; full output in ``run.output``
      - ``run.failed``        — run ended with an error; read ``run.error``

    Args:
        events_url: Full URL or path (starting with ``/``) to the SSE endpoint.

    Yields:
        dict: Parsed SSE event objects, each with at minimum a ``type`` key.
    """
    # Resolve relative URLs
    if events_url.startswith("/"):
        events_url = _base_url() + events_url

    headers = {"Accept": "text/event-stream"}
    headers.update(_auth_header())

    req = urllib.request.Request(events_url, headers=headers, method="GET")
    logger.debug("SSE stream: %s", events_url)

    with urllib.request.urlopen(req, timeout=300) as resp:
        buffer = ""
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace")
            buffer += line

            # SSE events are separated by blank lines
            if "\n\n" in buffer or "\r\n\r\n" in buffer:
                chunks = buffer.replace("\r\n", "\n").split("\n\n")
                # Last chunk may be incomplete – keep it in buffer
                buffer = chunks[-1]
                for chunk in chunks[:-1]:
                    event = _parse_sse_chunk(chunk)
                    if event:
                        yield event


def _parse_sse_chunk(chunk: str) -> Optional[dict]:
    """
    Parse a single SSE chunk into a dict.

    Each chunk is a series of `field: value` lines. We are only interested
    in `data:` lines which Headless Bob emits as JSON.

    Args:
        chunk: Raw multi-line SSE chunk string.

    Returns:
        Parsed dict, or None if no data line found.
    """
    data_lines = []
    for line in chunk.strip().splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        return None
    raw_data = "\n".join(data_lines)
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        # Return raw string wrapped in a dict for non-JSON data lines
        return {"type": "raw", "content": raw_data}


# ---------------------------------------------------------------------------
# Thread operations
# ---------------------------------------------------------------------------

def get_capabilities() -> ServerCapabilities:
    """
    Retrieve server status and capabilities from GET /api/v1/capabilities.

    Returns:
        ServerCapabilities dataclass populated from the response.
    """
    data = _request("GET", "/api/v1/capabilities")
    return ServerCapabilities(
        version=data.get("version", ""),
        bob_version=data.get("bob_version", ""),
        max_concurrent=data.get("max_concurrent", 0),
        max_queued=data.get("max_queued", 0),
        run_timeout_ms=data.get("run_timeout_ms", 0),
        extra=data,
    )


def list_threads(search: str = "", limit: int = 50) -> list[Thread]:
    """
    List conversation threads from GET /api/v1/threads.

    Args:
        search: Optional search string to filter threads by title.
        limit:  Maximum number of threads to return.

    Returns:
        List of Thread dataclasses.
    """
    params: dict = {"limit": limit}
    if search:
        params["search"] = search
    qs = urllib.parse.urlencode(params)
    data = _request("GET", f"/api/v1/threads?{qs}")
    threads = []
    for item in data.get("items", []):
        threads.append(Thread(
            id=item["id"],
            title=item.get("title", ""),
            created_at=item.get("created_at", ""),
            archived=item.get("archived", False),
            message_count=item.get("message_count", 0),
        ))
    return threads


def create_thread(title: str) -> Thread:
    """
    Create a new conversation thread via POST /api/v1/threads.

    Args:
        title: Human-readable title for the new thread.

    Returns:
        Newly created Thread dataclass.
    """
    data = _request("POST", "/api/v1/threads", {"title": title})
    return Thread(
        id=data["id"],
        title=data.get("title", title),
        created_at=data.get("created_at", ""),
    )


def delete_thread(thread_id: str) -> None:
    """
    Delete a thread and its workspace via DELETE /api/v1/threads/{id}.

    Args:
        thread_id: ID of the thread to delete.
    """
    _request("DELETE", f"/api/v1/threads/{thread_id}")
    logger.info("Deleted thread %s", thread_id)


def rename_thread(thread_id: str, new_title: str) -> Thread:
    """
    Rename a thread via PATCH /api/v1/threads/{id}.

    Args:
        thread_id: Target thread ID.
        new_title: New title string.

    Returns:
        Updated Thread dataclass.
    """
    data = _request("PATCH", f"/api/v1/threads/{thread_id}", {"title": new_title})
    return Thread(
        id=data["id"],
        title=data.get("title", new_title),
        created_at=data.get("created_at", ""),
        archived=data.get("archived", False),
    )


# ---------------------------------------------------------------------------
# Message / Run operations
# ---------------------------------------------------------------------------

def send_message(thread_id: str, prompt: str, mode: str = "") -> Run:
    """
    Post a prompt to a thread via POST /api/v1/threads/{id}/messages.

    This enqueues a new Bob Shell run. Poll or stream the run for results.

    The REST API only accepts {"content": <string>} — additionalProperties is
    false so any extra field (including "mode") causes a 400 Bad Request.
    The mode hint is prepended to the prompt text instead when provided.

    Args:
        thread_id: Target thread ID.
        prompt:    The task or question for Bob Shell.
        mode:      Optional mode hint prepended to the prompt text
                   (e.g. 'ask', 'plan'). Ignored when 'agent' (default).

    Returns:
        Run dataclass with initial status and events_url for streaming.
    """
    # API only allows {"content": <string>} — no extra fields accepted.
    # Prepend mode as a natural-language instruction when not the default.
    if mode and mode != "agent":
        content = f"[Mode: {mode}] {prompt}"
    else:
        content = prompt

    data = _request("POST", f"/api/v1/threads/{thread_id}/messages", {"content": content})
    # Response shape: {"thread": {...}, "run": {"run_id": "...", ...}, "events_url": "..."}
    run_data = data.get("run", {})
    run_id = run_data.get("run_id", "")
    return Run(
        run_id=run_id,
        status=run_data.get("status", "queued"),
        thread_id=thread_id,
        events_url=data.get("events_url", f"/api/v1/runs/{run_id}/events"),
    )


def get_run(run_id: str) -> Run:
    """
    Get the current status and result of a run via GET /api/v1/runs/{id}.

    Args:
        run_id: ID of the run to inspect.

    Returns:
        Run dataclass with current status and, if completed, result fields.
    """
    data = _request("GET", f"/api/v1/runs/{run_id}")
    stats = data.get("stats", {}) or {}
    return Run(
        run_id=data.get("run_id", run_id),
        status=data.get("status", ""),
        thread_id=data.get("thread_id", ""),
        last_message=data.get("last_message", ""),
        duration_ms=stats.get("duration_ms", 0),
        total_tokens=stats.get("total_tokens", 0),
        tool_calls=stats.get("tool_calls", 0),
        error=data.get("error", ""),
    )


def cancel_run(run_id: str) -> None:
    """
    Cancel an active run via POST /api/v1/runs/{id}/cancel.

    Args:
        run_id: ID of the run to cancel.
    """
    _request("POST", f"/api/v1/runs/{run_id}/cancel")
    logger.info("Cancelled run %s", run_id)


def list_messages(thread_id: str) -> list[dict]:
    """
    List conversation turns in a thread via GET /api/v1/threads/{id}/messages.

    Args:
        thread_id: Target thread ID.

    Returns:
        List of message dicts (role, content, created_at, run_id, etc.).
    """
    data = _request("GET", f"/api/v1/threads/{thread_id}/messages")
    return data.get("items", [])


def list_workspace_files(thread_id: str) -> list[WorkspaceFile]:
    """
    List files in the thread's isolated workspace directory.

    Args:
        thread_id: Target thread ID.

    Returns:
        List of WorkspaceFile dataclasses.
    """
    data = _request("GET", f"/api/v1/threads/{thread_id}/files")
    files = []
    for item in data.get("items", []):
        files.append(WorkspaceFile(
            path=item.get("path", ""),
            size=item.get("size", 0),
        ))
    return files


def download_workspace_file(thread_id: str, file_path: str) -> bytes:
    """
    Download a file from the thread workspace.

    Args:
        thread_id: Target thread ID.
        file_path: Relative path of the file within the workspace.

    Returns:
        Raw file bytes.
    """
    encoded_path = urllib.parse.quote(file_path, safe="")
    url = _base_url() + f"/api/v1/threads/{thread_id}/files/download?path={encoded_path}"
    headers = {"Accept": "*/*"}
    headers.update(_auth_header())
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()
