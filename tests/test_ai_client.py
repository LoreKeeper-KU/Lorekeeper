# Authored By Saif Altamimi 31/10/2026
"""Tests for shared/ai_client.py.

These start a tiny FAKE AI server on your own computer, so they are free,
fast, and need no API key or internet. They check that AIClient sends the
right requests and handles the replies (and errors) correctly.
"""
import base64
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image
from pydantic import BaseModel

from shared.ai_client import AIClient, AIClientError
from shared.schemas import VisualReport


def tiny_png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "silver").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class FakeAIServer(BaseHTTPRequestHandler):
    """Pretends to be an OpenAI-compatible API."""

    requests_seen = []  # every request the client sent: (path, body)
    chat_replies = []  # queued replies for /chat/completions
    fail_next = []  # queued status codes to fail with

    def log_message(self, *args):  # keep test output quiet
        pass

    def _reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.requests_seen.append((self.path, None, self.headers.get("Authorization")))
        if self.path == "/v1/models":
            self._reply(200, {"data": [{"id": "model-b"}, {"id": "model-a"}]})
        else:
            self._reply(404, {"error": {"message": "not found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        body = json.loads(raw) if "json" in content_type else raw
        self.requests_seen.append((self.path, body, self.headers.get("Authorization")))

        if self.fail_next:
            status = self.fail_next.pop(0)
            return self._reply(status, {"error": {"message": f"fake error {status}"}})

        if self.path == "/v1/chat/completions":
            text = self.chat_replies.pop(0) if self.chat_replies else "Hello from the fake model"
            self._reply(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})
        elif self.path == "/v1/embeddings":
            self._reply(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        elif self.path in ("/v1/images/generations", "/v1/images/edits"):
            self._reply(200, {"data": [{"b64_json": tiny_png_b64()}]})
        else:
            self._reply(404, {"error": {"message": "not found"}})


@pytest.fixture
def ai():
    FakeAIServer.requests_seen = []
    FakeAIServer.chat_replies = []
    FakeAIServer.fail_next = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAIServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    yield AIClient(api_key="test-key", base_url=base_url, max_retries=1)
    server.shutdown()


def last_request():
    return FakeAIServer.requests_seen[-1]


# --- connection ------------------------------------------------------------

def test_missing_api_key_gives_clear_error(monkeypatch):
    monkeypatch.setattr("shared.config.AI_API_KEY", None)
    with pytest.raises(AIClientError, match="No API key"):
        AIClient()


def test_list_models_sends_key(ai):
    assert ai.list_models() == ["model-a", "model-b"]
    assert last_request()[2] == "Bearer test-key"


# --- text -------------------------------------------------------------------

def test_generate_text(ai):
    reply = ai.generate_text("You are a storyteller.", "Describe a castle.")
    assert reply == "Hello from the fake model"
    path, body, _ = last_request()
    assert path == "/v1/chat/completions"
    assert body["messages"][0] == {"role": "system", "content": "You are a storyteller."}
    assert body["messages"][1] == {"role": "user", "content": "Describe a castle."}


class Character(BaseModel):
    name: str
    hair_color: str


def test_generate_structured_returns_model(ai):
    FakeAIServer.chat_replies = ['```json\n{"name": "Amina", "hair_color": "black"}\n```']
    result = ai.generate_structured("Extract the character.", "Amina has black hair.", Character)
    assert result == Character(name="Amina", hair_color="black")
    body = last_request()[1]
    assert body["response_format"]["json_schema"]["name"] == "Character"


def test_generate_structured_retries_once_on_bad_json(ai):
    FakeAIServer.chat_replies = ['{"name": "Amina"}', '{"name": "Amina", "hair_color": "black"}']
    result = ai.generate_structured("Extract.", "Amina has black hair.", Character)
    assert result.hair_color == "black"
    assert len(FakeAIServer.requests_seen) == 2


def test_generate_structured_gives_up_after_two_bad_replies(ai):
    FakeAIServer.chat_replies = ['{"name": "Amina"}', "not json at all"]
    with pytest.raises(AIClientError, match="did not match Character"):
        ai.generate_structured("Extract.", "Amina.", Character)


# --- embeddings ---------------------------------------------------------------

def test_embed_text(ai):
    assert ai.embed_text("Amina defends the castle") == [0.1, 0.2, 0.3]
    assert last_request()[0] == "/v1/embeddings"


# --- images -------------------------------------------------------------------

def test_generate_image_saves_file(ai, tmp_path):
    out = tmp_path / "scene_001.png"
    path = ai.generate_image("A castle at dawn", output_path=str(out))
    assert path == str(out)
    assert Image.open(path).size == (8, 8)


def test_edit_image_uploads_file(ai, tmp_path):
    original = tmp_path / "v1.png"
    Image.new("RGB", (8, 8), "gold").save(original)
    path = ai.edit_image(str(original), "Make the armor silver", output_path=str(tmp_path / "v2.png"))
    assert Image.open(path).size == (8, 8)
    path_sent, body, _ = last_request()
    assert path_sent == "/v1/images/edits"
    assert b"Make the armor silver" in body


def test_analyze_image_sends_image(ai, tmp_path):
    image = tmp_path / "scene.png"
    Image.new("RGB", (8, 8), "gray").save(image)
    answer = ai.analyze_image(str(image), "What colour is the armor?")
    assert answer == "Hello from the fake model"
    content = last_request()[1]["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_analyze_image_with_schema(ai, tmp_path):
    image = tmp_path / "scene.png"
    Image.new("RGB", (8, 8), "gray").save(image)
    FakeAIServer.chat_replies = [json.dumps({
        "image_path": str(image), "consistent": False,
        "issues": ["Armor is gold, not silver."], "evidence_fact_ids": ["F004"],
    })]
    report = ai.analyze_image(str(image), "Check the armor.", schema=VisualReport)
    assert isinstance(report, VisualReport)
    assert report.consistent is False


def test_analyze_missing_image_gives_clear_error(ai):
    with pytest.raises(AIClientError, match="Image not found"):
        ai.analyze_image("does/not/exist.png", "Describe it.")


# --- error handling -------------------------------------------------------------

def test_temporary_error_is_retried(ai):
    FakeAIServer.fail_next = [503]
    assert ai.generate_text("x", "y") == "Hello from the fake model"
    assert len(FakeAIServer.requests_seen) == 2


def test_permanent_error_gives_clear_message(ai):
    FakeAIServer.fail_next = [401]
    with pytest.raises(AIClientError, match="401.*fake error 401"):
        ai.generate_text("x", "y")
