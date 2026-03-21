"""Groq LLM client for fast open-model inference."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from new_osworld.agents.llm_clients.base import LLMClient
from new_osworld.logging_setup import get_logger

logger = get_logger("llm.groq")

_MODEL_MAP = {
    "llama3-70b": "llama3-70b-8192",
}


class GroqClient(LLMClient):
    """Client for the Groq API.

    Reads ``GROQ_API_KEY`` from the environment.
    """

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        from groq import Groq

        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        text_msgs = _to_text_only(messages)
        api_model = _MODEL_MAP.get(self.model, self.model)

        for attempt in range(20):
            try:
                logger.info("Calling Groq model: %s (attempt %d)", api_model, attempt + 1)
                resp = client.chat.completions.create(
                    messages=text_msgs,
                    model=api_model,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    temperature=temperature,
                )
                return resp.choices[0].message.content
            except Exception:
                if attempt == 0:
                    text_msgs = [text_msgs[0], text_msgs[-1]]
                else:
                    last = text_msgs[-1].get("content", "")
                    text_msgs[-1]["content"] = " ".join(last.split()[:-500])

        return ""


def _to_text_only(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    result = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "\n".join(p["text"] for p in content if p.get("type") == "text")
        result.append({"role": msg["role"], "content": content})
    return result
