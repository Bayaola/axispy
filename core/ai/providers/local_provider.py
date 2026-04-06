"""Local LLM provider (Ollama, LM Studio, or any OpenAI-compatible local server)."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Dict, List

from core.ai.providers.base import AIProvider
from core.logger import get_logger

_logger = get_logger("ai.local")


class LocalLLMProvider(AIProvider):
    """Provider for local LLM servers that expose an OpenAI-compatible API.

    Works with:
    - Ollama (default: http://localhost:11434/v1)
    - LM Studio (default: http://localhost:1234/v1)
    - Any OpenAI-compatible local server
    """

    def __init__(self, model: str = "llama3",
                 base_url: str = "http://localhost:11434/v1"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.7,
             max_tokens: int = 4096, **kwargs) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            data = self._request("/chat/completions", body)
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            _logger.error("Local LLM chat error", error=str(e))
            return f"[Error] {e}"

    def chat_stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096, **kwargs):
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as e:
            _logger.error("Local LLM stream error", error=str(e))
            yield f"\n[Error] {e}"

    def is_available(self) -> bool:
        try:
            url = f"{self.base_url}/models"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def model_name(self) -> str:
        return f"{self.model} (local)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, body: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
