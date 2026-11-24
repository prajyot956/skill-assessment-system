"""Configurable LLM provider. The app never depends on it: callers catch AIUnavailable and fall back."""
import json
import logging
import time

import requests
from flask import current_app

log = logging.getLogger(__name__)


class AIUnavailable(Exception):
    """AI is not configured, failed, or returned something unusable."""


def extract_json(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else text
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise AIUnavailable("no JSON in response")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise AIUnavailable("invalid JSON in response") from e


class AnthropicProvider:
    url = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: int):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete_json(self, system: str, user: str, max_tokens: int = 2500, retries: int = 2):
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        last = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(self.url, headers=headers, json=body, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                    time.sleep(min(2 ** attempt, 4))
                    continue
                if r.status_code != 200:
                    raise AIUnavailable(f"HTTP {r.status_code}")
                blocks = r.json().get("content", [])
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                return extract_json(text)
            except requests.RequestException as e:
                last = type(e).__name__
                time.sleep(min(2 ** attempt, 4))
        raise AIUnavailable(f"AI request failed ({last})")


class GroqProvider:
    """Groq Cloud provider — uses the OpenAI-compatible chat completions endpoint."""
    url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout: int):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete_json(self, system: str, user: str, max_tokens: int = 2500, retries: int = 2):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Ask the model to respond with JSON so we can reliably parse it
            "response_format": {"type": "json_object"},
        }
        last = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(self.url, headers=headers, json=body, timeout=self.timeout)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                    time.sleep(min(2 ** attempt, 4))
                    continue
                if r.status_code == 404 and "model" in r.text.lower():
                    fallback_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
                    found = False
                    for fb in fallback_models:
                        if fb != self.model:
                            log.warning("Groq model %s unavailable, switching to %s", self.model, fb)
                            self.model = fb
                            body["model"] = fb
                            found = True
                            break
                    if found:
                        continue
                if r.status_code != 200:
                    raise AIUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
                choices = r.json().get("choices", [])
                if not choices:
                    raise AIUnavailable("empty choices in Groq response")
                text = choices[0].get("message", {}).get("content", "")
                return extract_json(text)
            except requests.RequestException as e:
                last = type(e).__name__
                time.sleep(min(2 ** attempt, 4))
        raise AIUnavailable(f"AI request failed ({last})")


def get_provider():
    """Returns a configured provider, or None when AI is not configured."""
    cfg = current_app.config
    provider_name = cfg.get("AI_PROVIDER", "none")
    api_key = cfg.get("AI_API_KEY")
    model = cfg.get("AI_MODEL")
    timeout = cfg.get("AI_TIMEOUT_SECONDS", 30)

    if not api_key:
        return None

    if provider_name == "anthropic":
        return AnthropicProvider(api_key, model, timeout)

    if provider_name == "groq":
        return GroqProvider(api_key, model, timeout)

    return None


def ai_enabled() -> bool:
    return get_provider() is not None
