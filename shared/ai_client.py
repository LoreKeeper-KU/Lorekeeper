# Authored By Saif Altamimi 31/10/2026

"""Shared AI client for LoreKeeper.

Every module calls AI through this class instead of a vendor library.
It sends plain HTTP requests in the widely supported "OpenAI-compatible"
format, so the provider and models can be switched in .env
(AI_BASE_URL, TEXT_MODEL, ...) without changing any code.

Usage:
    from shared.ai_client import AIClient
    ai = AIClient()
    text = ai.generate_text("You are a storyteller.", "Describe a castle.")
"""
import base64
import json
import mimetypes
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from shared import config

T = TypeVar("T", bound=BaseModel)

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # temporary problems worth retrying


class AIClientError(Exception):
    """Raised when an AI call fails. The message says what went wrong."""

    def __init__(self, message, *, public_message="The AI service request failed.", status_code=None):
        super().__init__(message)
        self.public_message = public_message
        self.status_code = status_code


class AIClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or config.AI_API_KEY
        self.base_url = (base_url or config.AI_BASE_URL).rstrip("/")
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES if max_retries is None else max_retries
        if not self.api_key:
            raise AIClientError("No API key found. Add AI_API_KEY to your .env file.")

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Send one HTTP request, retrying temporary failures, and return JSON."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method, url, headers=headers, timeout=self.timeout, **kwargs
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                detail = ("The AI request timed out. Try again or increase REQUEST_TIMEOUT."
                          if isinstance(exc, requests.Timeout)
                          else "Could not connect to the AI provider. Check the network and API_BASE_URL.")
                raise AIClientError(f"Could not reach {url}: {exc}", public_message=detail) from exc

            if _should_retry(response) and attempt < self.max_retries:
                time.sleep(2**attempt)  # wait 1s, 2s, 4s... then try again
                continue
            if response.status_code >= 400:
                raise AIClientError(
                    f"{method} {url} failed ({response.status_code}): {_error_text(response)}",
                    public_message=_public_api_error(response), status_code=response.status_code,
                )
            try:
                return response.json()
            except ValueError as exc:
                raise AIClientError(f"{url} did not return JSON: {response.text[:200]}",
                                    public_message="The AI provider returned an invalid response instead of JSON.") from exc

        raise AIClientError(f"{url} failed after {self.max_retries + 1} attempts")  # pragma: no cover

    def _chat(self, messages: list[dict], model: str, **extra) -> str:
        """Call /chat/completions and return the reply text."""
        body = {"model": model, "messages": messages, **extra}
        result = self._request("POST", "chat/completions", json=body)
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError(f"Unexpected chat response: {str(result)[:300]}") from exc
        if not content:
            raise AIClientError("The model returned an empty reply.")
        return content

    def _chat_structured(self, messages: list[dict], model: str, schema: type[T]) -> T:
        """Ask for JSON matching `schema`, validate it, and retry once if invalid."""
        schema_json = schema.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema_json, "strict": False},
        }
        # Also describe the schema in words, for providers that ignore response_format.
        guide = {
            "role": "system",
            "content": "Reply ONLY with a JSON object that matches this JSON schema:\n"
            + json.dumps(schema_json),
        }
        attempt_messages = [guide, *messages]

        for attempt in range(2):
            content = self._chat(attempt_messages, model, response_format=response_format)
            try:
                return schema.model_validate_json(_strip_code_fence(content))
            except ValidationError as exc:
                if attempt == 1:
                    raise AIClientError(
                        f"Model output did not match {schema.__name__}: {exc}"
                    ) from exc
                # Show the model its mistake and ask again.
                attempt_messages = [
                    *attempt_messages,
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"That JSON was invalid: {exc}. Fix it and reply with JSON only."},
                ]
        raise AIClientError("Structured generation failed")  # pragma: no cover

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """Return the model names this API key can use (free; good connection test)."""
        result = self._request("GET", "models")
        return sorted(model["id"] for model in result.get("data", []))

    def generate_text(self, instructions: str, prompt: str) -> str:
        """Generate text. `instructions` = how to behave, `prompt` = the task."""
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ]
        return self._chat(messages, config.TEXT_MODEL)

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """Return an assistant message: ordinary text or native function calls."""
        result = self._request("POST", "chat/completions", json={
            "model": config.TEXT_MODEL, "messages": messages,
            "tools": tools, "tool_choice": "auto", "parallel_tool_calls": False,
        })
        try:
            message = result["choices"][0]["message"]
            content = message.get("content")
            calls = message.get("tool_calls", [])
            if content is not None and not isinstance(content, str):
                raise ValueError("Invalid content")
            if not isinstance(calls, list):
                raise ValueError("Invalid tool calls")
            if not calls and not (content and content.strip()):
                raise ValueError("Empty assistant reply")
            for call in calls:
                if (call.get("type") != "function" or not isinstance(call.get("id"), str) or not call["id"]
                        or not isinstance(call["function"]["name"], str)
                        or not isinstance(call["function"]["arguments"], str)):
                    raise ValueError("Invalid function call")
            if len({call["id"] for call in calls}) != len(calls):
                raise ValueError("Duplicate function call IDs")
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise AIClientError("The provider returned an invalid tool-call response.") from exc
        reply = {"role": "assistant", "content": content}
        if calls:
            reply["tool_calls"] = calls
        return reply

    def generate_structured(self, instructions: str, prompt: str, schema: type[T]) -> T:
        """Generate data that fits a Pydantic schema and return it as that model."""
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ]
        return self._chat_structured(messages, config.TEXT_MODEL, schema)

    def embed_text(self, text: str) -> list[float]:
        """Turn text into a list of numbers (an embedding) for semantic search."""
        result = self._request(
            "POST", "embeddings", json={"model": config.EMBEDDING_MODEL, "input": text}
        )
        try:
            return result["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError(f"Unexpected embedding response: {str(result)[:300]}") from exc

    def generate_image(self, prompt: str, output_path: Optional[str] = None) -> str:
        """Generate an image, save it as a file, and return the file path."""
        body = {"model": config.IMAGE_MODEL, "prompt": prompt, "size": config.IMAGE_SIZE, "n": 1}
        result = self._request("POST", "images/generations", json=body)
        return self._save_image(result, output_path)

    def edit_image(self, image_path: str, prompt: str, output_path: Optional[str] = None) -> str:
        """Edit an existing image following `prompt`; save and return the new path."""
        path = Path(image_path)
        if not path.exists():
            raise AIClientError(f"Image not found: {image_path}")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        with path.open("rb") as image_file:
            result = self._request(
                "POST",
                "images/edits",
                data={"model": config.IMAGE_MODEL, "prompt": prompt, "size": config.IMAGE_SIZE},
                files={"image": (path.name, image_file, mime)},
            )
        return self._save_image(result, output_path)

    def analyze_image(self, image_path: str, prompt: str, schema: Optional[type[T]] = None):
        """Ask a vision model about an image.

        Returns text, or a Pydantic model if `schema` is given.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
                ],
            }
        ]
        if schema is None:
            return self._chat(messages, config.VISION_MODEL)
        return self._chat_structured(messages, config.VISION_MODEL, schema)

    # ------------------------------------------------------------------
    # Image file helpers
    # ------------------------------------------------------------------

    def _save_image(self, result: dict, output_path: Optional[str]) -> str:
        """Save the first image in an images API response and return its path."""
        try:
            item = result["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError(f"Unexpected image response: {str(result)[:300]}") from exc

        if item.get("b64_json"):
            image_bytes = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            try:
                download = requests.get(item["url"], timeout=self.timeout)
                download.raise_for_status()
            except requests.RequestException as exc:
                raise AIClientError(f"Could not download generated image: {exc}") from exc
            image_bytes = download.content
        else:
            raise AIClientError("Image response contained no image data.")

        if output_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = str(Path(config.OUTPUT_DIR) / f"image_{stamp}.png")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        return str(path)


# ----------------------------------------------------------------------
# Small helper functions
# ----------------------------------------------------------------------


def _error_text(response: requests.Response) -> str:
    """Pull a readable error message out of an error response."""
    try:
        body = response.json()
        error = body.get("error", body)
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error)
    except ValueError:
        return response.text[:300]


def _public_api_error(response: requests.Response) -> str:
    """Safe diagnostic categories, never provider text which may echo credentials."""
    status = response.status_code
    try:
        error = response.json().get("error", {})
        error = error if isinstance(error, dict) else {}
    except (ValueError, AttributeError):
        error = {}
    code = error.get("code")
    message = str(error.get("message", "")).casefold()
    if code in {"insufficient_quota", "billing_hard_limit_reached"}:
        detail = "The API account has insufficient credit or has reached its spending limit. Check API billing."
    elif code in {"moderation_blocked", "content_policy_violation"}:
        detail = "The image request was blocked by the provider's content checks. Revise the image prompt."
    elif "verif" in message and "organization" in message:
        detail = "The provider requires organization verification before this model can be used. Check your API organization's verification status."
    elif code == "model_not_found" or status == 404:
        detail = "The requested model or endpoint is unavailable to this API account. Check the model name and provider access."
    elif status == 401:
        detail = "The provider rejected the API credentials. Check the configured API key."
    elif status == 403:
        detail = "This API account is not permitted to use the requested model. Check model access and organization settings."
    elif status == 429:
        detail = "The provider rate limit was reached. Wait briefly before trying again."
    elif status >= 500:
        detail = "The AI provider had a server error. Try again later."
    else:
        detail = "The provider rejected the request settings. Check the configured model, image size, and endpoint compatibility."
    return f"{detail} (HTTP {status})"


def _should_retry(response: requests.Response) -> bool:
    if response.status_code not in RETRY_STATUS_CODES:
        return False
    try:
        error = response.json().get("error", {})
        if isinstance(error, dict) and (
            error.get("code") in {"insufficient_quota", "billing_hard_limit_reached", "moderation_blocked", "content_policy_violation"}
            or error.get("type") == "image_generation_user_error"
        ):
            return False
    except (ValueError, AttributeError):
        pass
    return True


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` fences some models wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _image_to_data_url(image_path: str) -> str:
    """Read an image file and encode it so it can be sent inside JSON."""
    path = Path(image_path)
    if not path.exists():
        raise AIClientError(f"Image not found: {image_path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"
