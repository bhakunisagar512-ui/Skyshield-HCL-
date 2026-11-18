"""LLM providers.

Each provider's generate() returns either a dict (structured output) or raw text
that the caller parses. Anthropic uses tool use, so the API returns a JSON object
matching the schema instead of free text; this removes broken-JSON failures.
Temporary API errors (rate limits, overload, 5xx) are retried with backoff.
"""
import logging
import time
from typing import Any, Protocol

import httpx

from app.config import get_settings

log = logging.getLogger("skyshield.llm")

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-4o-mini"}
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
MAX_ATTEMPTS = 4


class LLM(Protocol):
    name: str

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> dict | str: ...


def post_with_retry(url: str, *, headers: dict, payload: dict, timeout: float = 120,
                    sleep=time.sleep) -> httpx.Response:
    """POST, retrying temporary failures. Honours a numeric Retry-After header."""
    delay = 1.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"LLM API unreachable: {exc}") from exc
            log.warning("LLM request error (%s), retry %d", exc, attempt)
            sleep(delay)
            delay *= 2
            continue
        if resp.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
            wait = delay
            retry_after = resp.headers.get("retry-after", "")
            if retry_after.replace(".", "", 1).isdigit():
                wait = min(float(retry_after), 30.0)
            log.warning("LLM API %s, retry %d in %.1fs", resp.status_code, attempt, wait)
            sleep(wait)
            delay *= 2
            continue
        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise RuntimeError(f"LLM API error {resp.status_code}: {detail}")
        return resp
    raise RuntimeError("LLM API retries exhausted")  # pragma: no cover


class AnthropicLLM:
    TOOL_NAME = "submit_incident_assessment"

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model
        self.name = f"anthropic:{model}"

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> dict | str:
        resp = post_with_retry(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            payload={
                "model": self.model,
                "max_tokens": 2000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "tools": [{"name": self.TOOL_NAME,
                           "description": "Submit the incident summary and the measures to take.",
                           "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": self.TOOL_NAME},
            },
        )
        body = resp.json()
        for block in body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == self.TOOL_NAME:
                return block.get("input") or {}
        # no tool call (should not happen with tool_choice); return any text for the parser
        return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


class OpenAILLM:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model
        self.name = f"openai:{model}"

    def generate(self, system: str, user: str, schema: dict[str, Any]) -> dict | str:
        resp = post_with_retry(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload={"model": self.model, "response_format": {"type": "json_object"},
                     "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        return resp.json()["choices"][0]["message"]["content"]


def get_llm() -> LLM | None:
    """None means 'mock': the RAG service builds the result straight from the policies."""
    s = get_settings()
    provider = s.llm_provider.lower()
    if provider == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
        return AnthropicLLM(s.anthropic_api_key, s.llm_model or DEFAULT_MODELS["anthropic"])
    if provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai needs OPENAI_API_KEY")
        return OpenAILLM(s.openai_api_key, s.llm_model or DEFAULT_MODELS["openai"])
    return None
