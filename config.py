from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    project_root: Path
    config_dir: Path
    log_dir: Path
    audio_temp_dir: Path
    piper_voice: Path
    piper_voice_config: Path
    whisper_path: Path
    whisper_model: Path
    chat_model: str
    mic_sample_rate: int
    target_sample_rate: int
    whisper_threads: int
    ollama_url: str
    ollama_timeout: int
    ollama_temperature: float
    ollama_max_tokens: int
    assistant_name: str
    silence_threshold: float
    silence_duration: float
    max_record_seconds: float
    tts_rate: float
    log_level: str
    local_soul_path: Path
    cloud_soul_path: Path

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        project_root = Path(os.getenv("PROJECT_ROOT", "/home/raspi/2002"))
        config_dir = project_root / "config"
        log_dir = project_root / "logs"
        audio_temp_dir = _resolve_temp_dir()
        piper_voice = Path(
            os.getenv(
                "PIPER_VOICE",
                "/home/raspi/2002/piper/voices/en_US-hfc_female-medium.onnx",
            )
        )
        piper_voice_config = Path(
            os.getenv(
                "PIPER_VOICE_CONFIG",
                "/home/raspi/2002/piper/voices/en_US-hfc_female-medium.onnx.json",
            )
        )
        whisper_path = Path(
            os.getenv("WHISPER_PATH", "/home/raspi/2002/whisper.cpp/whisper-cli")
        )
        whisper_model = Path(
            os.getenv(
                "WHISPER_MODEL",
                "/home/raspi/2002/whisper.cpp/models/ggml-base.en.bin",
            )
        )
        assistant_name = os.getenv("ASSISTANT_NAME", "JARVIS")
        local_soul_path = Path(
            os.getenv("LOCAL_SOUL_PATH", str(config_dir / "local_soul.md"))
        )
        cloud_soul_path = Path(
            os.getenv("CLOUD_SOUL_PATH", str(config_dir / "cloud_soul.md"))
        )

        config = cls(
            project_root=project_root,
            config_dir=config_dir,
            log_dir=log_dir,
            audio_temp_dir=audio_temp_dir,
            piper_voice=piper_voice,
            piper_voice_config=piper_voice_config,
            whisper_path=whisper_path,
            whisper_model=whisper_model,
            chat_model=os.getenv("CHAT_MODEL", "qwen2.5:1.5b"),
            mic_sample_rate=int(os.getenv("MIC_SAMPLE_RATE", "16000")),
            target_sample_rate=int(os.getenv("TARGET_SAMPLE_RATE", "16000")),
            whisper_threads=int(os.getenv("WHISPER_THREADS", "4")),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat"),
            ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "120")),
            ollama_temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
            ollama_max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "512")),
            assistant_name=assistant_name,
            silence_threshold=float(os.getenv("SILENCE_THRESHOLD", "0.015")),
            silence_duration=float(os.getenv("SILENCE_DURATION", "1.2")),
            max_record_seconds=float(os.getenv("MAX_RECORD_SECONDS", "12")),
            tts_rate=float(os.getenv("TTS_RATE", "1.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            local_soul_path=local_soul_path,
            cloud_soul_path=cloud_soul_path,
        )
        config.ensure_directories()
        return config

    def ensure_directories(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if not self.audio_temp_dir.exists():
            self.audio_temp_dir.mkdir(parents=True, exist_ok=True)


def _resolve_temp_dir() -> Path:
    shm = Path("/dev/shm")
    if shm.exists() and os.access(shm, os.W_OK):
        return shm / "jarvis"
    return Path("/tmp/jarvis")
