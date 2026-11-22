import pytest
from unittest.mock import Mock
from shared.ai_client import AIClient, AIClientError


def test_native_tool_protocol_uses_auto_and_preserves_calls():
    ai = AIClient(api_key="test-key")
    message = {"role": "assistant", "content": None, "tool_calls": [{
        "id": "lookup", "type": "function", "function": {"name": "read_canon", "arguments": '{"query":"Mira"}'}
    }]}
    ai._request = Mock(return_value={"choices": [{"message": message}]})
    history = [{"role": "user", "content": "What do we know about Mira?"}]
    tools = [{"type": "function", "function": {"name": "read_canon"}}]
    assert ai.chat_with_tools(history, tools) == message
    body = ai._request.call_args.kwargs["json"]
    assert body["tool_choice"] == "auto"
    assert body["parallel_tool_calls"] is False
    assert body["messages"] == history
    assert body["tools"] == tools


def test_direct_text_response_is_accepted_without_calls():
    ai = AIClient(api_key="test-key")
    ai._request = Mock(return_value={"choices": [{"message": {"content": "Hello!"}}]})
    assert ai.chat_with_tools([], []) == {"role": "assistant", "content": "Hello!"}


@pytest.mark.parametrize("result", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]},
                                     {"choices": [{"message": {"tool_calls": [{}]}}]}])
def test_invalid_protocol_response_is_reported_without_provider_payload(result):
    ai = AIClient(api_key="test-key")
    ai._request = Mock(return_value=result)
    with pytest.raises(AIClientError, match="invalid tool-call response"):
        ai.chat_with_tools([], [])
