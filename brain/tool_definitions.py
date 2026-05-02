from __future__ import annotations

import datetime as dt
import os
import platform
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]


def _get_time(_: dict[str, Any]) -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _get_system_info(_: dict[str, Any]) -> str:
    cpu_count = os.cpu_count() or 0
    return f"platform={platform.platform()}, cpu_count={cpu_count}"


TOOLS: list[Tool] = [
    Tool(
        name="get_time",
        description="Get the current system local time (system timezone) in ISO format.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_get_time,
    ),
    Tool(
        name="get_system_info",
        description="Get basic system information about this Raspberry Pi.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=_get_system_info,
    ),
]


def get_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOLS
    ]


def get_tool_handlers() -> dict[str, Callable[[dict[str, Any]], str]]:
    return {tool.name: tool.handler for tool in TOOLS}
