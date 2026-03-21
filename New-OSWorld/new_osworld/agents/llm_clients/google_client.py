"""Google Gemini LLM client."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import backoff

from new_osworld.agents.llm_clients.base import LLMClient
from new_osworld.agents.utils.image_utils import decode_base64_to_pil
from new_osworld.logging_setup import get_logger

logger = get_logger("llm.google")


class GoogleClient(LLMClient):
    """Client for Google Gemini generative models.

    Reads ``GENAI_API_KEY`` from the environment.
    """

    @backoff.on_exception(
        backoff.constant,
        (Exception,),
        interval=30,
        max_tries=5,
    )
    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        import google.generativeai as genai

        api_key = os.environ.get("GENAI_API_KEY")
        if not api_key:
            raise RuntimeError("GENAI_API_KEY environment variable is not set.")
        genai.configure(api_key=api_key)

        role_map = {"assistant": "model", "user": "user", "system": "system"}
        gemini_messages: List[Dict[str, Any]] = []

        for msg in messages:
            parts: List[Any] = []
            for part in msg.get("content", []):
                if part["type"] == "image_url":
                    parts.insert(0, decode_base64_to_pil(part["image_url"]["url"]))
                elif part["type"] == "text":
                    parts.append(part["text"])
            gemini_messages.append({"role": role_map.get(msg["role"], "user"), "parts": parts})

        system_instruction = None
        if gemini_messages and gemini_messages[0]["role"] == "system":
            system_instruction = gemini_messages[0]["parts"][0] if gemini_messages[0]["parts"] else None
            gemini_messages.pop(0)

        logger.info("Calling Gemini model: %s", self.model)
        model = genai.GenerativeModel(self.model, system_instruction=system_instruction)
        response = model.generate_content(
            gemini_messages,
            generation_config={
                "candidate_count": 1,
                "top_p": top_p,
                "temperature": temperature,
            },
            safety_settings={
                "harassment": "block_none",
                "hate": "block_none",
                "sex": "block_none",
                "danger": "block_none",
            },
            request_options={"timeout": 120},
        )
        return response.text
