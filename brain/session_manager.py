from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from config import Config


class SessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session_id = time.strftime("%Y%m%d-%H%M%S")
        self.history: list[dict[str, Any]] = []
        self.log_path = self.config.log_dir / f"session_{self.session_id}.jsonl"
        self._write_runtime_config()

    def _write_runtime_config(self) -> None:
        runtime_config = {
            "session_id": self.session_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        path = self.config.config_dir / "config.json"
        path.write_text(json.dumps(runtime_config, indent=2), encoding="utf-8")

    def add_message(self, role: str, content: str) -> None:
        entry = {"role": role, "content": content}
        self.history.append(entry)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_history(self) -> list[dict[str, Any]]:
        return list(self.history)
