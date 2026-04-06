"""OpenRouter provider — unified access to 300+ models with tool calling and model discovery."""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from core.ai.providers.base import AIProvider
from core.logger import get_logger

_logger = get_logger("ai.openrouter")


class OpenRouterProvider(AIProvider):
    """Provider that talks to OpenRouter's OpenAI-compatible API.

    Supports any model available on OpenRouter (DeepSeek, Claude, GPT,
    Gemini, Llama, Mistral, etc.), including tool/function calling
    and the special ``openrouter/auto`` model selector.

    Get a free API key at: https://openrouter.ai/settings/keys
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str = "",
                 model: str = "deepseek/deepseek-chat:free",
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
             max_tokens: int = 4096,
             tools: Optional[List[Dict]] = None) -> str:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        for attempt in range(self.MAX_RETRIES):
            try:
                data = self._request("/chat/completions", body)
                choice = data["choices"][0]
                msg = choice.get("message", {})

                # Check for tool calls
                if msg.get("tool_calls"):
                    return json.dumps({
                        "tool_calls": msg["tool_calls"],
                        "content": msg.get("content", ""),
                    })

                return msg.get("content", "")
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                _logger.error("OpenRouter chat error", error=str(e))
                return f"[Error] {e}"
            except Exception as e:
                _logger.error("OpenRouter chat error", error=str(e))
                return f"[Error] {e}"
        return "[Error] Max retries exceeded"

    def chat_stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096,
                    tools: Optional[List[Dict]] = None):
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        url = f"{self.base_url}/chat/completions"
        headers = self._headers()
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )

        for attempt in range(self.MAX_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    tool_calls_buffer: Dict[int, Dict] = {}
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

                            # Handle tool call deltas
                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_buffer:
                                        tool_calls_buffer[idx] = {
                                            "id": tc.get("id", ""),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    buf = tool_calls_buffer[idx]
                                    if tc.get("id"):
                                        buf["id"] = tc["id"]
                                    fn = tc.get("function", {})
                                    if fn.get("name"):
                                        buf["function"]["name"] = fn["name"]
                                    if fn.get("arguments"):
                                        buf["function"]["arguments"] += fn["arguments"]

                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

                    # If tool calls were collected, yield them as a special JSON marker
                    if tool_calls_buffer:
                        tc_list = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer.keys())]
                        yield f"\n__TOOL_CALLS__{json.dumps(tc_list)}"

                return  # success
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                _logger.error("OpenRouter stream error", error=str(e))
                yield f"\n[Error] {e}"
                return
            except Exception as e:
                _logger.error("OpenRouter stream error", error=str(e))
                yield f"\n[Error] {e}"
                return

    def chat_with_tools(self, messages: List[Dict[str, str]],
                        tools: List[Dict],
                        temperature: float = 0.7,
                        max_tokens: int = 4096) -> Dict[str, Any]:
        """Non-streaming chat that returns structured response including tool calls.

        Returns dict with keys: 'content', 'tool_calls' (list or None), 'finish_reason'.
        """
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "tools": tools,
            "tool_choice": "auto",
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                data = self._request("/chat/completions", body)
                choice = data["choices"][0]
                msg = choice.get("message", {})
                return {
                    "content": msg.get("content", ""),
                    "tool_calls": msg.get("tool_calls"),
                    "finish_reason": choice.get("finish_reason", "stop"),
                }
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s")
                    time.sleep(delay)
                    continue
                return {"content": f"[Error] {e}", "tool_calls": None, "finish_reason": "error"}
            except Exception as e:
                return {"content": f"[Error] {e}", "tool_calls": None, "finish_reason": "error"}
        return {"content": "[Error] Max retries exceeded", "tool_calls": None, "finish_reason": "error"}

    def is_available(self) -> bool:
        return bool(self.api_key)

    def model_name(self) -> str:
        return self.model

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

    def fetch_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from OpenRouter API.

        Returns a list of model dicts with keys: id, name, description,
        context_length, pricing, etc.
        """
        url = f"{self.base_url}/models"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data", [])
        except Exception as e:
            _logger.error("Failed to fetch models", error=str(e))
            return []

    def fetch_free_models(self) -> List[Dict[str, Any]]:
        """Fetch only free models from OpenRouter."""
        models = self.fetch_models()
        free = []
        for m in models:
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "1"))
            completion_price = float(pricing.get("completion", "1"))
            if prompt_price == 0 and completion_price == 0:
                free.append(m)
        return free

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://axispy-engine.dev",
            "X-Title": "AxisPy Engine AI Assistant",
        }

    def _request(self, endpoint: str, body: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = self._headers()
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
