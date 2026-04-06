"""Anthropic API provider (Claude)."""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Dict, List

from core.ai.providers.base import AIProvider
from core.logger import get_logger

_logger = get_logger("ai.anthropic")


class AnthropicProvider(AIProvider):
    """Provider that talks to the Anthropic Claude API."""

    def __init__(self, api_key: str = "", model: str = "claude-3-5-sonnet-latest",
                 base_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds

    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple[List[Dict], str]:
        """Convert standard messages to Anthropic's format and extract system prompt."""
        anthropic_messages = []
        system_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                # Anthropic takes system prompt as a top-level parameter, not in messages list.
                # If there are multiple, concatenate.
                system_prompt += content + "\n\n"
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
        
        system_prompt = system_prompt.strip()
        return anthropic_messages, system_prompt

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.7,
             max_tokens: int = 4096, **kwargs) -> str:
        
        anth_messages, system_prompt = self._convert_messages(messages)
        
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anth_messages,
        }
        if system_prompt:
            body["system"] = system_prompt
            
        url = f"{self.base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        for attempt in range(self.MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode("utf-8"),
                    headers=headers, method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content_blocks = data.get("content", [])
                    if content_blocks:
                        return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                    return ""
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                try:
                    error_data = e.read().decode("utf-8")
                    _logger.error("Anthropic chat error", error=error_data)
                    return f"[Error] {e}: {error_data}"
                except:
                    _logger.error("Anthropic chat error", error=str(e))
                    return f"[Error] {e}"
            except Exception as e:
                _logger.error("Anthropic chat error", error=str(e))
                return f"[Error] {e}"
        return "[Error] Max retries exceeded"

    def chat_stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096, **kwargs):
        anth_messages, system_prompt = self._convert_messages(messages)
        
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anth_messages,
            "stream": True
        }
        if system_prompt:
            body["system"] = system_prompt
            
        url = f"{self.base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
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
                        if not line or not line.startswith("data: "):
                            continue
                        payload = line[len("data: "):].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            chunk_type = chunk.get("type", "")
                            
                            if chunk_type == "content_block_delta":
                                delta = chunk.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text_chunk = delta.get("text", "")
                                    if text_chunk:
                                        yield text_chunk
                            elif chunk_type in ("message_stop", "error"):
                                if chunk_type == "error":
                                    err = chunk.get("error", {})
                                    yield f"\n[Error] {err.get('message', 'Unknown API Error')}"
                                break
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                return  # success, stop retrying
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                try:
                    error_data = e.read().decode("utf-8")
                    _logger.error("Anthropic stream error", error=error_data)
                    yield f"\n[Error] {e}: {error_data}"
                except:
                    _logger.error("Anthropic stream error", error=str(e))
                    yield f"\n[Error] {e}"
                return
            except Exception as e:
                _logger.error("Anthropic stream error", error=str(e))
                yield f"\n[Error] {e}"
                return

    def is_available(self) -> bool:
        return bool(self.api_key)

    def model_name(self) -> str:
        return self.model
