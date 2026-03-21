"""LLM client factory -- pick the right backend from a model name."""

from __future__ import annotations

from typing import Dict, Any

from new_osworld.agents.llm_clients.base import LLMClient


def create_llm_client(model: str) -> LLMClient:
    """Return an :class:`LLMClient` implementation appropriate for *model*.

    Args:
        model: Model identifier string (e.g. ``"gpt-4o"``, ``"claude-3-opus"``).

    Raises:
        ValueError: If no client matches the model prefix.
    """
    lower = model.lower()

    if lower.startswith("azure-gpt"):
        from new_osworld.agents.llm_clients.openai_client import AzureOpenAIClient
        return AzureOpenAIClient(model)

    if lower.startswith("gpt") or lower.startswith("o1") or lower.startswith("o3"):
        from new_osworld.agents.llm_clients.openai_client import OpenAIClient
        return OpenAIClient(model)

    if lower.startswith("claude"):
        from new_osworld.agents.llm_clients.anthropic_client import AnthropicClient
        return AnthropicClient(model)

    if lower.startswith("gemini"):
        from new_osworld.agents.llm_clients.google_client import GoogleClient
        return GoogleClient(model)

    if lower.startswith("llama"):
        from new_osworld.agents.llm_clients.groq_client import GroqClient
        return GroqClient(model)

    if lower.startswith("qwen"):
        from new_osworld.agents.llm_clients.dashscope_client import DashScopeClient
        return DashScopeClient(model)

    if lower.startswith("mistral"):
        from new_osworld.agents.llm_clients.openai_client import TogetherClient
        return TogetherClient(model)

    raise ValueError(
        f"No LLM client registered for model '{model}'.  "
        f"Supported prefixes: gpt, azure-gpt, claude, gemini, llama, qwen, mistral."
    )


__all__ = ["LLMClient", "create_llm_client"]
