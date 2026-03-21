"""Abstract base for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMClient(ABC):
    """Thin interface wrapping a chat-completion API.

    Subclasses handle provider-specific payload formatting, authentication,
    and error retry.
    """

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        """Send a chat-completion request and return the assistant text.

        Args:
            messages: OpenAI-style message list.
            max_tokens: Maximum generation tokens.
            temperature: Sampling temperature.
            top_p: Nucleus-sampling threshold.

        Returns:
            The model's response text.

        Raises:
            Exception: On unrecoverable API errors.
        """
