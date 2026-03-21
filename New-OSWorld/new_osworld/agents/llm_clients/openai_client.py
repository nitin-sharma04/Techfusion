"""OpenAI and OpenAI-compatible LLM clients."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import backoff
import requests
from requests.exceptions import SSLError

from new_osworld.agents.llm_clients.base import LLMClient
from new_osworld.logging_setup import get_logger

logger = get_logger("llm.openai")


class OpenAIClient(LLMClient):
    """Client for the OpenAI Chat Completions API (``gpt-*`` models).

    Reads ``OPENAI_API_KEY`` and optionally ``OPENAI_BASE_URL`` from the
    environment.
    """

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
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        logger.info("Calling OpenAI model: %s", self.model)
        resp = requests.post(url, headers=headers, json=payload, timeout=120)

        if resp.status_code != 200:
            body = resp.json()
            if body.get("error", {}).get("code") == "context_length_exceeded":
                logger.warning("Context too long -- retrying with trimmed history.")
                payload["messages"] = [messages[0], messages[-1]]
                retry = requests.post(url, headers=headers, json=payload, timeout=120)
                if retry.status_code == 200:
                    return retry.json()["choices"][0]["message"]["content"]
            logger.error("OpenAI API error (%d): %s", resp.status_code, resp.text)
            time.sleep(5)
            return ""

        return resp.json()["choices"][0]["message"]["content"]


class AzureOpenAIClient(LLMClient):
    """Client for Azure-hosted OpenAI endpoints.

    Reads ``AZURE_OPENAI_API_KEY`` and ``AZURE_OPENAI_ENDPOINT`` from ``.env``
    or the environment.
    """

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
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        headers = {"Content-Type": "application/json", "api-key": api_key}
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        logger.info("Calling Azure OpenAI model: %s", self.model)
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)

        if resp.status_code != 200:
            body = resp.json()
            if body.get("error", {}).get("code") == "context_length_exceeded":
                logger.warning("Context too long -- retrying with trimmed history.")
                payload["messages"] = [messages[0], messages[-1]]
                retry = requests.post(endpoint, headers=headers, json=payload, timeout=120)
                if retry.status_code == 200:
                    return retry.json()["choices"][0]["message"]["content"]
            logger.error("Azure API error (%d): %s", resp.status_code, resp.text)
            return ""

        return resp.json()["choices"][0]["message"]["content"]


class TogetherClient(LLMClient):
    """Client for Together AI (Mistral and other open models).

    Reads ``TOGETHER_API_KEY`` from the environment.
    """

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: int = 1500,
        temperature: float = 1.0,
        top_p: float = 0.9,
    ) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["TOGETHER_API_KEY"],
            base_url="https://api.together.xyz",
        )
        text_messages = _to_text_only(messages)

        for attempt in range(20):
            try:
                logger.info("Calling Together model: %s (attempt %d)", self.model, attempt + 1)
                resp = client.chat.completions.create(
                    messages=text_messages,
                    model=self.model,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    temperature=temperature,
                )
                return resp.choices[0].message.content
            except Exception:
                if attempt == 0:
                    text_messages = [text_messages[0], text_messages[-1]]
                else:
                    last = text_messages[-1].get("content", "")
                    text_messages[-1]["content"] = " ".join(last.split()[:-500])
        return ""


def _to_text_only(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Strip image content from messages for text-only models."""
    result = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            texts = [p["text"] for p in content if p.get("type") == "text"]
            content = "\n".join(texts)
        result.append({"role": msg["role"], "content": content})
    return result
