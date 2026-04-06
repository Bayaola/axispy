"""DeepSeek provider via OpenRouter (free tier available)."""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Dict, List

from core.ai.providers.base import AIProvider
from core.logger import get_logger

_logger = get_logger("ai.deepseek")


class DeepSeekProvider(AIProvider):
    """Provider that talks to DeepSeek models via OpenRouter.

    Uses the OpenAI-compatible endpoint at openrouter.ai.
    Requires an API key from OpenRouter (free tier available).
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str = "", model: str = "deepseek/deepseek-chat:free",
                 base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds

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
        for attempt in range(self.MAX_RETRIES):
            try:
                data = self._request("/chat/completions", body)
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                _logger.error("DeepSeek chat error", error=str(e))
                return f"[Error] {e}"
            except Exception as e:
                _logger.error("DeepSeek chat error", error=str(e))
                return f"[Error] {e}"
        return "[Error] Max retries exceeded"

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
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        for attempt in range(self.MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
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
                return  # success, stop retrying
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                _logger.error("DeepSeek stream error", error=str(e))
                yield f"\n[Error] {e}"
                return
            except Exception as e:
                _logger.error("DeepSeek stream error", error=str(e))
                yield f"\n[Error] {e}"
                return

    def is_available(self) -> bool:
        return bool(self.api_key)

    def model_name(self) -> str:
        return f"{self.model} (DeepSeek)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, endpoint: str, body: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
