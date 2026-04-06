"""Gemini API provider."""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Dict, List

from core.ai.providers.base import AIProvider
from core.logger import get_logger

_logger = get_logger("ai.gemini")


class GoogleProvider(AIProvider):
    """Provider that talks to the Google API."""

    def __init__(self, api_key: str = "", model: str = "gemini-2.5-flash",
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2.0  # seconds

    def _convert_messages(self, messages: List[Dict[str, str]]) -> dict:
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = {
                    "parts": [{"text": content}]
                }
            else:
                gemini_role = "model" if role == "assistant" else "user"
                # Combine adjacent messages with same role if needed, but for simple use case just append
                if contents and contents[-1]["role"] == gemini_role:
                    contents[-1]["parts"][0]["text"] += "\n" + content
                else:
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]
                    })
        
        body = {"contents": contents}
        if system_instruction:
            body["system_instruction"] = system_instruction
            
        return body

    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.7,
             max_tokens: int = 4096, **kwargs) -> str:
        body = self._convert_messages(messages)
        body["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return ""
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _logger.warning(f"Rate limited (429), retrying in {delay:.0f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                try:
                    error_data = e.read().decode("utf-8")
                    _logger.error("Gemini chat error", error=error_data)
                    return f"[Error] {e}: {error_data}"
                except:
                    _logger.error("Gemini chat error", error=str(e))
                    return f"[Error] {e}"
            except Exception as e:
                _logger.error("Gemini chat error", error=str(e))
                return f"[Error] {e}"
        return "[Error] Max retries exceeded"

    def chat_stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096, **kwargs):
        body = self._convert_messages(messages)
        body["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        
        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
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
                            # Gemini doesn't always send [DONE] standard, but check valid json
                            chunk = json.loads(payload)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    content = parts[0].get("text", "")
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
                try:
                    error_data = e.read().decode("utf-8")
                    _logger.error("Gemini stream error", error=error_data)
                    yield f"\n[Error] {e}: {error_data}"
                except:
                    _logger.error("Gemini stream error", error=str(e))
                    yield f"\n[Error] {e}"
                return
            except Exception as e:
                _logger.error("Gemini stream error", error=str(e))
                yield f"\n[Error] {e}"
                return

    def is_available(self) -> bool:
        return bool(self.api_key)

    def model_name(self) -> str:
        return self.model
