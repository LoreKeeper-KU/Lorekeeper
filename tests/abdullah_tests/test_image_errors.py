import json
from unittest.mock import Mock

import pytest
import requests

from shared.ai_client import AIClient, AIClientError, _public_api_error
from shared.schemas import CanonFact, VisualAsset
from canon_memory.canon_store import CanonStore
from generation_engine.models import ChatRequest
from generation_engine.ui_backend import handle_message


def response(status, code=None, message="secret-provider-text"):
    result = Mock(status_code=status)
    result.json.return_value = {"error": {"code": code, "message": message}}
    return result


@pytest.mark.parametrize("status,code,expected", [
    (401, "invalid_api_key", "credentials"),
    (403, None, "not permitted"),
    (404, "model_not_found", "unavailable"),
    (429, "insufficient_quota", "credit"),
    (429, "rate_limit_exceeded", "rate limit"),
    (400, "moderation_blocked", "content checks"),
    (500, None, "server error"),
])
def test_safe_error_categories_do_not_echo_raw_provider_messages(status, code, expected):
    message = _public_api_error(response(status, code))
    assert expected in message
    assert f"HTTP {status}" in message
    assert "secret" not in message


def test_quota_error_is_not_retried(monkeypatch):
    post = Mock(return_value=response(429, "insufficient_quota"))
    monkeypatch.setattr("shared.ai_client.requests.request", post)
    client = AIClient(api_key="test", max_retries=2)
    with pytest.raises(AIClientError) as exc:
        client.generate_image("a sword")
    assert "credit" in exc.value.public_message
    assert exc.value.status_code == 429
    post.assert_called_once()


def test_timeout_is_actionable(monkeypatch):
    monkeypatch.setattr("shared.ai_client.requests.request", Mock(side_effect=requests.Timeout("secret")))
    with pytest.raises(AIClientError) as exc:
        AIClient(api_key="test", max_retries=0).generate_image("sword")
    assert "REQUEST_TIMEOUT" in exc.value.public_message
    assert "secret" not in exc.value.public_message


@pytest.mark.parametrize("vision_failure", [False, True])
def test_image_error_reaches_ui_and_preserves_generated_asset(tmp_path, monkeypatch, vision_failure):
    monkeypatch.chdir(tmp_path)
    CanonStore().add_fact("world_001", CanonFact(id="n", subject="vader", predicate="name", object="Darth Vader"))
    failure = AIClientError("secret", public_message="Account model access denied. (HTTP 403)", status_code=403)
    generate = Mock(return_value=VisualAsset(image_path="image.png", prompt="Vader")) if vision_failure else Mock(side_effect=failure)
    monkeypatch.setattr("multimodal.visuals.generate_visual", generate)
    monkeypatch.setattr("multimodal.visuals.check_visual_facts", Mock(side_effect=failure))
    def call(prompt, ident):
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": ident, "type": "function", "function": {
                "name": "generate_image", "arguments": json.dumps({"prompt": prompt, "target_message_id": ""})
            }
        }]}
    client = Mock()
    client.chat_with_tools.side_effect = [call("Draw Darth Vader", "first"),
                                         call("Try drawing Darth Vader again", "retry"),
                                         {"role": "assistant", "content": "There was an error."}]
    result = handle_message(ChatRequest("Draw Darth Vader"), client=client)
    assert "HTTP 403" in result.message.content
    assert "secret" not in result.message.content
    assert result.message.visual_status == "error"
    assert bool(result.message.asset) == vision_failure
    assert ("Image verification failed" if vision_failure else "Image generation failed") in result.message.content
    generate.assert_called_once()  # No repeated image billing during model retries.
