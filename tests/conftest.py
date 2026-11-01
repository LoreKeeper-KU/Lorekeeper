import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from shared.ai_client import AIClient


class FakeChatApi:
    """A tiny local OpenAI-compatible server plus a real shared AIClient pointed at it."""

    def __init__(self):
        self.reply_text = ""
        self.requests_seen = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                api.requests_seen.append(json.loads(raw))
                body = json.dumps(
                    {"choices": [{"message": {"content": api.reply_text}}]}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = AIClient(
            api_key="test-key", base_url=f"http://127.0.0.1:{self.server.server_port}/v1"
        )

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_chat_api():
    api = FakeChatApi()
    yield api
    api.stop()
