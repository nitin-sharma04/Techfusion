"""DashScope (Alibaba Cloud / Qwen) LLM client."""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import Any, Dict, List

from new_osworld.agents.llm_clients.base import LLMClient
from new_osworld.agents.utils.image_utils import save_base64_to_tempfile
from new_osworld.logging_setup import get_logger

logger = get_logger("llm.dashscope")

_MULTIMODAL_MODELS = {"qwen-vl-plus", "qwen-vl-max"}
_TEXT_MODELS = {
    "qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-0428",
    "qwen-max-0403", "qwen-max-0107", "qwen-max-longcontext",
}


class DashScopeClient(LLMClient):
    """Client for Alibaba DashScope Qwen models.

    Reads ``DASHSCOPE_API_KEY`` from the environment (set by the dashscope
    library automatically).
    """

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        import dashscope

        qwen_msgs = self._convert_messages(messages)

        for attempt in range(20):
            try:
                logger.info("Calling DashScope model: %s (attempt %d)", self.model, attempt + 1)

                if self.model in _MULTIMODAL_MODELS:
                    resp = dashscope.MultiModalConversation.call(
                        model=self.model, messages=qwen_msgs,
                        result_format="message",
                        max_length=max_tokens, top_p=top_p, temperature=temperature,
                    )
                elif self.model in _TEXT_MODELS:
                    resp = dashscope.Generation.call(
                        model=self.model, messages=qwen_msgs,
                        result_format="message",
                        max_length=max_tokens, top_p=top_p, temperature=temperature,
                    )
                else:
                    raise ValueError(f"Unsupported Qwen model: {self.model}")

                if resp.status_code == HTTPStatus.OK:
                    choices = resp["output"]["choices"]
                    content = choices[0]["message"]["content"]
                    if isinstance(content, list):
                        return content[0]["text"]
                    return content

                logger.error(
                    "DashScope error (%s): %s", resp.status_code, resp.message
                )
                raise RuntimeError(resp.message)
            except Exception:
                if attempt == 0:
                    qwen_msgs = [qwen_msgs[0], qwen_msgs[-1]]
                else:
                    for part in qwen_msgs[-1].get("content", []):
                        if "text" in part:
                            part["text"] = " ".join(part["text"].split()[:-500])
        return ""

    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted = []
        for msg in messages:
            content: List[Dict[str, str]] = []
            for part in msg.get("content", []):
                if part["type"] == "image_url":
                    path = save_base64_to_tempfile(part["image_url"]["url"])
                    content.append({"image": f"file://{path}"})
                elif part["type"] == "text":
                    content.append({"text": part["text"]})
            converted.append({"role": msg["role"], "content": content})
        return converted
