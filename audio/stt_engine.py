from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path

from config import Config


class WhisperCppSTT:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)

    def _resolve_whisper_path(self) -> Path:
        if self.config.whisper_path.exists():
            return self.config.whisper_path
        candidates = [
            self.config.whisper_path.parent / "main",
            self.config.whisper_path.parent / "whisper",
        ]
        for candidate in candidates:
            if candidate.exists():
                self.logger.warning(
                    "Whisper binary not found at %s, using %s instead.",
                    self.config.whisper_path,
                    candidate,
                )
                return candidate
        return self.config.whisper_path

    def transcribe(self, wav_path: Path) -> str:
        whisper_path = self._resolve_whisper_path()
        if not whisper_path.exists():
            raise FileNotFoundError(f"Whisper binary not found: {whisper_path}")
        if not self.config.whisper_model.exists():
            raise FileNotFoundError(f"Whisper model not found: {self.config.whisper_model}")

        output_prefix = self.config.audio_temp_dir / f"whisper_{uuid.uuid4().hex}"
        output_txt = output_prefix.with_suffix(".txt")

        cmd = [
            str(whisper_path),
            "-m",
            str(self.config.whisper_model),
            "-f",
            str(wav_path),
            "-t",
            str(self.config.whisper_threads),
            "-nt",
            "-otxt",
            "-of",
            str(output_prefix),
        ]

        self.logger.info("Running whisper.cpp transcription...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.logger.error("Whisper.cpp failed: %s", result.stderr.strip())
            raise RuntimeError("Whisper.cpp transcription failed")

        if output_txt.exists():
            text = output_txt.read_text(encoding="utf-8").strip()
            output_txt.unlink(missing_ok=True)
        else:
            text = result.stdout.strip()

        return text
