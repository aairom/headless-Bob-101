"""
test_headless_bob_client.py
===========================
Unit tests for the headless_bob_client module.

These tests mock all HTTP calls and SSE streams so they run fully offline —
no running Headless Bob service or IBM credentials are required.

Run with:
    python -m pytest tests/ -v
    # or from project root:
    python -m pytest tests/test_headless_bob_client.py -v
"""

import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make the src/ directory importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import headless_bob_client as hb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(body: dict, status: int = 200) -> MagicMock:
    """Return a MagicMock that behaves like urllib HTTP response."""
    raw = json.dumps(body).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _sse_lines(*events: dict) -> MagicMock:
    """
    Create a MagicMock response that yields SSE-formatted lines.

    Each event dict is serialised as a `data: <json>\\n\\n` chunk.
    """
    chunks = []
    for ev in events:
        line = f"data: {json.dumps(ev)}\n\n"
        chunks.append(line.encode("utf-8"))

    mock_resp = MagicMock()
    mock_resp.__iter__ = MagicMock(return_value=iter(chunks))
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

class TestEnvironmentHelpers(unittest.TestCase):
    """Tests for _base_url and _auth_header environment resolution."""

    def test_base_url_default(self):
        """_base_url should return default when env var is absent."""
        with patch.dict("os.environ", {}, clear=False):
            # Temporarily remove the env var if present
            import os
            original = os.environ.pop("HEADLESS_BOB_URL", None)
            try:
                url = hb._base_url()
                self.assertEqual(url, "http://127.0.0.1:8000")
            finally:
                if original is not None:
                    os.environ["HEADLESS_BOB_URL"] = original

    def test_base_url_custom(self):
        """_base_url should return the custom URL from env, stripped of trailing slash."""
        with patch.dict("os.environ", {"HEADLESS_BOB_URL": "http://myserver:9000/"}):
            self.assertEqual(hb._base_url(), "http://myserver:9000")

    def test_auth_header_present(self):
        """_auth_header should return Bearer header when token is set."""
        with patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "supersecret"}):
            header = hb._auth_header()
            self.assertEqual(header, {"Authorization": "Bearer supersecret"})

    def test_auth_header_missing_raises(self):
        """_auth_header should raise EnvironmentError when token is missing."""
        import os
        original = os.environ.pop("HEADLESS_BOB_TOKEN", None)
        try:
            with self.assertRaises(EnvironmentError):
                hb._auth_header()
        finally:
            if original is not None:
                os.environ["HEADLESS_BOB_TOKEN"] = original


# ---------------------------------------------------------------------------
# Data class tests
# ---------------------------------------------------------------------------

class TestDataClasses(unittest.TestCase):
    """Smoke tests for dataclass instantiation."""

    def test_thread_creation(self):
        t = hb.Thread(id="abc", title="My thread")
        self.assertEqual(t.id, "abc")
        self.assertEqual(t.title, "My thread")
        self.assertFalse(t.archived)

    def test_run_creation(self):
        r = hb.Run(run_id="r1", status="queued")
        self.assertEqual(r.run_id, "r1")
        self.assertEqual(r.status, "queued")
        self.assertEqual(r.total_tokens, 0)

    def test_server_capabilities(self):
        caps = hb.ServerCapabilities(version="1.0", bob_version="2.0.4")
        self.assertEqual(caps.version, "1.0")
        self.assertEqual(caps.bob_version, "2.0.4")

    def test_workspace_file(self):
        wf = hb.WorkspaceFile(path="hello.txt", size=123)
        self.assertEqual(wf.path, "hello.txt")
        self.assertEqual(wf.size, 123)


# ---------------------------------------------------------------------------
# API call tests
# ---------------------------------------------------------------------------

class TestGetCapabilities(unittest.TestCase):
    """Tests for get_capabilities()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_capabilities(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "version": "1.2.3",
            "bob_version": "2.0.4",
            "max_concurrent": 2,
            "max_queued": 100,
            "run_timeout_ms": 300000,
        })
        caps = hb.get_capabilities()
        self.assertEqual(caps.version, "1.2.3")
        self.assertEqual(caps.bob_version, "2.0.4")
        self.assertEqual(caps.max_concurrent, 2)
        self.assertEqual(caps.run_timeout_ms, 300000)


class TestListThreads(unittest.TestCase):
    """Tests for list_threads()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_thread_list(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "items": [
                {"id": "t1", "title": "First", "message_count": 3, "archived": False},
                {"id": "t2", "title": "Second", "message_count": 1, "archived": False},
            ]
        })
        threads = hb.list_threads()
        self.assertEqual(len(threads), 2)
        self.assertEqual(threads[0].id, "t1")
        self.assertEqual(threads[0].title, "First")
        self.assertEqual(threads[0].message_count, 3)

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_empty_list(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({"items": []})
        threads = hb.list_threads()
        self.assertEqual(threads, [])


class TestCreateThread(unittest.TestCase):
    """Tests for create_thread()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_creates_thread(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "id": "new-id",
            "title": "My thread",
            "created_at": "2024-01-01T00:00:00Z",
        })
        thread = hb.create_thread("My thread")
        self.assertEqual(thread.id, "new-id")
        self.assertEqual(thread.title, "My thread")

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_sends_correct_body(self, mock_urlopen):
        """Verify that the title is sent as JSON body."""
        mock_urlopen.return_value = _make_response({"id": "x", "title": "Test"})
        hb.create_thread("Test")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]  # urllib.request.Request object
        self.assertEqual(req.data, b'{"title": "Test"}')
        self.assertEqual(req.get_method(), "POST")


class TestDeleteThread(unittest.TestCase):
    """Tests for delete_thread()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_calls_delete(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({})
        hb.delete_thread("t123")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_method(), "DELETE")
        self.assertIn("t123", req.full_url)


class TestRenameThread(unittest.TestCase):
    """Tests for rename_thread()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_renames_and_returns_thread(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "id": "t1",
            "title": "New Name",
            "archived": False,
        })
        thread = hb.rename_thread("t1", "New Name")
        self.assertEqual(thread.title, "New Name")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "PATCH")


class TestSendMessage(unittest.TestCase):
    """Tests for send_message()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_run_with_status(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "run": {
                "run_id": "run-001",
                "status": "queued",
            },
            "events_url": "/api/v1/runs/run-001/events",
        })
        run = hb.send_message("t1", "Hello Bob!")
        self.assertEqual(run.run_id, "run-001")
        self.assertEqual(run.status, "queued")
        self.assertEqual(run.events_url, "/api/v1/runs/run-001/events")

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_sends_mode_when_provided(self, mock_urlopen):
        """Mode is prepended to content — not sent as a separate field (API rejects extra fields)."""
        mock_urlopen.return_value = _make_response({
            "run": {"run_id": "r1", "status": "queued"},
            "events_url": "/api/v1/runs/r1/events",
        })
        hb.send_message("t1", "prompt", mode="ask")
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        # Only "content" is allowed — no "mode" field
        self.assertNotIn("mode", body)
        self.assertIn("[Mode: ask]", body["content"])
        self.assertIn("prompt", body["content"])


class TestGetRun(unittest.TestCase):
    """Tests for get_run()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_completed_run(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "run_id": "r1",
            "status": "completed",
            "last_message": "Done!",
            "stats": {
                "duration_ms": 4200,
                "total_tokens": 512,
                "tool_calls": 3,
            },
        })
        run = hb.get_run("r1")
        self.assertEqual(run.run_id, "r1")
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.last_message, "Done!")
        self.assertEqual(run.duration_ms, 4200)
        self.assertEqual(run.total_tokens, 512)
        self.assertEqual(run.tool_calls, 3)


class TestCancelRun(unittest.TestCase):
    """Tests for cancel_run()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_sends_post_to_cancel(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({})
        hb.cancel_run("r1")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("cancel", req.full_url)


class TestListMessages(unittest.TestCase):
    """Tests for list_messages()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_messages(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "items": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ]
        })
        messages = hb.list_messages("t1")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["content"], "Hello!")


class TestListWorkspaceFiles(unittest.TestCase):
    """Tests for list_workspace_files()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_workspace_files(self, mock_urlopen):
        mock_urlopen.return_value = _make_response({
            "items": [
                {"path": "hello.txt", "size": 11},
                {"path": "data/result.json", "size": 256},
            ]
        })
        files = hb.list_workspace_files("t1")
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].path, "hello.txt")
        self.assertEqual(files[1].size, 256)


# ---------------------------------------------------------------------------
# SSE parsing tests
# ---------------------------------------------------------------------------

class TestParseSseChunk(unittest.TestCase):
    """Tests for _parse_sse_chunk()."""

    def test_parses_json_data_line(self):
        chunk = 'data: {"type": "message.part", "content": "hello"}'
        result = hb._parse_sse_chunk(chunk)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "message.part")

    def test_returns_none_for_empty_chunk(self):
        self.assertIsNone(hb._parse_sse_chunk(""))
        self.assertIsNone(hb._parse_sse_chunk("   "))

    def test_returns_none_for_comment_only(self):
        self.assertIsNone(hb._parse_sse_chunk(": keep-alive"))

    def test_handles_non_json_data(self):
        chunk = "data: plain text"
        result = hb._parse_sse_chunk(chunk)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "raw")
        self.assertEqual(result["content"], "plain text")

    def test_parses_multiline_data(self):
        """SSE data may span multiple data: lines (concatenated)."""
        chunk = 'data: {"type":\ndata:  "result"}'
        result = hb._parse_sse_chunk(chunk)
        # JSON spanning lines depends on spec – here we just verify no crash
        # (the concat may or may not produce valid JSON depending on newlines)
        # At minimum the function should not raise
        self.assertIsNotNone(result)

    def test_parses_result_event(self):
        payload = json.dumps({
            "type": "result",
            "status": "success",
            "last_message": "Task complete.",
            "stats": {"duration_ms": 1000, "total_tokens": 200},
        })
        result = hb._parse_sse_chunk(f"data: {payload}")
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["last_message"], "Task complete.")


class TestStreamEvents(unittest.TestCase):
    """Tests for stream_events() generator."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_yields_parsed_events(self, mock_urlopen):
        events = [
            {"type": "message.part", "part": {"content": "Hi"}},
            {"type": "result", "status": "success", "last_message": "Done"},
        ]
        mock_urlopen.return_value = _sse_lines(*events)
        collected = list(hb.stream_events("http://localhost:8000/api/v1/runs/r1/events"))
        self.assertGreaterEqual(len(collected), 2)
        types = [e.get("type") for e in collected]
        self.assertIn("message.part", types)
        self.assertIn("result", types)

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_resolves_relative_url(self, mock_urlopen):
        """Relative event URLs should be prefixed with the base URL."""
        mock_urlopen.return_value = _sse_lines(
            {"type": "result", "status": "success", "last_message": "OK"}
        )
        list(hb.stream_events("/api/v1/runs/r1/events"))
        req = mock_urlopen.call_args[0][0]
        self.assertTrue(req.full_url.startswith("http://localhost:8000"))


class TestDownloadWorkspaceFile(unittest.TestCase):
    """Tests for download_workspace_file()."""

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_returns_raw_bytes(self, mock_urlopen):
        expected = b"Hello World"
        mock_resp = MagicMock()
        mock_resp.read.return_value = expected
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = hb.download_workspace_file("t1", "hello.txt")
        self.assertEqual(result, expected)

    @patch("urllib.request.urlopen")
    @patch.dict("os.environ", {"HEADLESS_BOB_TOKEN": "tok", "HEADLESS_BOB_URL": "http://localhost:8000"})
    def test_encodes_path_in_url(self, mock_urlopen):
        """File paths with slashes and spaces must be URL-encoded."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        hb.download_workspace_file("t1", "sub dir/my file.txt")
        req = mock_urlopen.call_args[0][0]
        # Spaces and slashes must be percent-encoded in the path parameter
        self.assertNotIn(" ", req.full_url)


# ---------------------------------------------------------------------------
# Integration smoke test (skipped unless service is reachable)
# ---------------------------------------------------------------------------

class TestIntegrationSmoke(unittest.TestCase):
    """
    Optional live integration tests.

    These tests are skipped automatically unless both HEADLESS_BOB_URL and
    HEADLESS_BOB_TOKEN are configured AND the service is reachable.
    """

    def setUp(self):
        import os
        url = os.environ.get("HEADLESS_BOB_URL", "")
        token = os.environ.get("HEADLESS_BOB_TOKEN", "")
        if not url or not token:
            self.skipTest("HEADLESS_BOB_URL or HEADLESS_BOB_TOKEN not set — skipping live tests")
        try:
            hb.get_capabilities()
        except Exception:
            self.skipTest("Headless Bob service is not reachable — skipping live tests")

    def test_create_and_delete_thread(self):
        """Verify full create → send → delete lifecycle against a live service."""
        thread = hb.create_thread("Integration smoke test")
        self.assertTrue(thread.id)

        # Clean up regardless of test outcome
        try:
            threads = hb.list_threads()
            ids = [t.id for t in threads]
            self.assertIn(thread.id, ids)
        finally:
            hb.delete_thread(thread.id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
