from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from config import Config


class OllamaClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client = httpx.Client(timeout=self.config.ollama_timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": messages,
            "options": {
                "temperature": self.config.ollama_temperature,
                "num_predict": self.config.ollama_max_tokens,
            },
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        self.logger.info("Sending request to Ollama...")
        response = self._client.post(self.config.ollama_url, json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
