from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from audio.emotion_detector import EmotionResult
from config import Config


class ConversationRouter:
    def __init__(
        self,
        config: Config,
        ollama_client,
        tool_definitions: list[dict[str, Any]],
        tool_handlers: dict[str, Callable[[dict[str, Any]], str]],
        session_manager,
    ) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.ollama_client = ollama_client
        self.tool_definitions = tool_definitions
        self.tool_handlers = tool_handlers
        self.session_manager = session_manager
        self.soul_text = self._load_soul(config.local_soul_path)

    def _load_soul(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        return f"You are {self.config.assistant_name}."

    def _system_prompt(self) -> str:
        return (
            f"{self.soul_text}\n\n"
            f"You are {self.config.assistant_name}, a Raspberry Pi 4 assistant."
        )

    def handle(self, user_text: str, emotion: EmotionResult) -> str:
        self.session_manager.add_message("user", user_text)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "system", "content": f"Detected emotion: {emotion.label}."},
        ]
        messages.extend(self.session_manager.get_history())

        response = self.ollama_client.chat(messages, tools=self.tool_definitions)
        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                name = function.get("name")
                arguments = function.get("arguments", {})
                handler = self.tool_handlers.get(name)
                if not handler:
                    continue
                result = handler(arguments if isinstance(arguments, dict) else {})
                messages.append(
                    {"role": "tool", "name": name, "content": result}
                )
            response = self.ollama_client.chat(messages, tools=self.tool_definitions)
            message = response.get("message", {})

        content = message.get("content", "").strip()
        if content:
            self.session_manager.add_message("assistant", content)
        return content
