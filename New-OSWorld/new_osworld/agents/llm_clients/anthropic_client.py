"""Anthropic Claude LLM client."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import backoff
import requests
from requests.exceptions import SSLError

from new_osworld.agents.llm_clients.base import LLMClient
from new_osworld.logging_setup import get_logger

logger = get_logger("llm.anthropic")


class AnthropicClient(LLMClient):
    """Client for the Anthropic Messages API (``claude-*`` models).

    Reads ``ANTHROPIC_API_KEY`` from the environment.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    @backoff.on_exception(
        backoff.constant,
        (SSLError, requests.ConnectionError, requests.Timeout),
        interval=30,
        max_tries=10,
    )
    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        claude_msgs = self._convert_messages(messages)
        headers = {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": claude_msgs,
            "top_p": top_p,
        }

        logger.info("Calling Anthropic model: %s", self.model)
        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=120)

        if resp.status_code != 200:
            logger.error("Anthropic API error (%d): %s", resp.status_code, resp.text)
            time.sleep(5)
            return ""

        return resp.json()["content"][0]["text"]

    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-format messages to Anthropic format.

        Claude does not support ``system`` as a message role, so we
        prepend it to the first ``user`` message.
        """
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            content_parts: List[Dict[str, Any]] = []
            for part in msg.get("content", []):
                if part["type"] == "image_url":
                    b64 = part["image_url"]["url"].replace("data:image/png;base64,", "")
                    content_parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    })
                elif part["type"] == "text":
                    content_parts.append({"type": "text", "text": part["text"]})
            converted.append({"role": msg["role"], "content": content_parts})

        if converted and converted[0]["role"] == "system":
            sys_part = converted[0]["content"][0]
            converted[1]["content"].insert(0, sys_part)
            converted.pop(0)

        return converted
