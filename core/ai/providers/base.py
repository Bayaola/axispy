"""Abstract base class for AI chat providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional


class AIProvider(ABC):
    """Interface that all AI providers must implement."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]],
             temperature: float = 0.7,
             max_tokens: int = 4096, **kwargs) -> str:
        """Send messages and return a complete response (blocking)."""
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 4096, **kwargs):
        """Yield response chunks as they arrive (generator)."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and reachable."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the display name of the current model."""
        ...
