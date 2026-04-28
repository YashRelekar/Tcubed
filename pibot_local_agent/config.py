"""
Configuration management for Jansky.
Supports env-var overrides for all hardware device selections.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json

# Auto-detect the project root so paths work from any location.
_PROJECT_ROOT = str(Path(__file__).parent.resolve())


@dataclass
class Config:
    """Application configuration."""

    # Paths
    project_root: str = _PROJECT_ROOT
    assets_path: str = ""  # resolved in __post_init__

    # Audio - Piper TTS (using piper-tts Python package)
    piper_voice: str = ""  # resolved in __post_init__

    # Whisper.cpp
    whisper_path: str = "/usr/local/bin/whisper-cpp"
    whisper_model: str = ""  # resolved in __post_init__

    # Models
    chat_model: str = "qwen2.5:1.5b"

    # Wake word
    wake_word_model: str = ""  # resolved in __post_init__
    wake_word_threshold: float = 0.5

    # Microphone settings
    # Native sample rate of the reSpeaker XVF3800 is 48 kHz.
    mic_sample_rate: int = 48000

    # Mic/speaker device name substrings (can be overridden by env vars).
    # MIC_NAME defaults to "XVF3800" for the reSpeaker XVF3800 4-Mic Array.
    # SPEAKER_NAME defaults to "" which means use the system default sink
    # (correct for PipeWire + Bluetooth A2DP on Pi OS Bookworm).
    mic_name: str = "XVF3800"
    speaker_name: str = ""

    # Camera settings
    # CAMERA_INDEX 0 = first camera (IMX219 MIPI on Pi 5).
    camera_index: int = 0
    libcamera_device: str = ""

    # Local location default
    local_location: str = "Kingston, CA"
    target_sample_rate: int = 16000

    # API Keys (loaded from environment)
    openweather_api_key: str = ""
    moonshot_api_key: str = ""
    newsapi_key: str = ""

    # Soul/personality files
    local_soul_path: str = ""  # resolved in __post_init__
    cloud_soul_path: str = ""  # resolved in __post_init__

    # Display
    display_width: int = 800
    display_height: int = 480
    use_framebuffer: bool = True

    # Features
    enable_streaming_tts: bool = False
    enable_ui: bool = True

    def __post_init__(self):
        """Resolve path defaults relative to project_root."""
        root = self.project_root
        if not self.assets_path:
            self.assets_path = os.path.join(root, "assets", "face")
        if not self.piper_voice:
            self.piper_voice = os.path.join(
                root, "piper", "voices", "en_GB-semaine-medium.onnx"
            )
        if not self.whisper_model:
            self.whisper_model = os.path.join(
                root, "whisper.cpp", "models", "ggml-base.en-q5_0.bin"
            )
        if not self.wake_word_model:
            self.wake_word_model = os.path.join(
                root, "models", "wake_word", "Hey_Jansky.onnx"
            )
        if not self.local_soul_path:
            self.local_soul_path = os.path.join(root, "config", "local_soul.md")
        if not self.cloud_soul_path:
            self.cloud_soul_path = os.path.join(root, "config", "cloud_soul.md")

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from file and environment."""
        config = cls()

        # Load from JSON file if it exists
        if config_path is None:
            config_path = os.path.join(config.project_root, "config", "config.json")

        if Path(config_path).exists():
            with open(config_path) as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # Load from .env file if present (lowest priority — env vars win)
        env_path = os.path.join(config.project_root, ".env")
        if Path(env_path).exists():
            config._load_env_file(env_path)

        # Override with environment variables (highest priority)
        config.openweather_api_key = os.getenv(
            "OPENWEATHER_API_KEY", config.openweather_api_key
        )
        config.moonshot_api_key = os.getenv(
            "MOONSHOT_API_KEY", config.moonshot_api_key
        )
        config.newsapi_key = os.getenv("NEWSAPI_KEY", config.newsapi_key)

        # Hardware device overrides via env vars
        config.mic_name = os.getenv("MIC_NAME", config.mic_name)
        config.speaker_name = os.getenv("SPEAKER_NAME", config.speaker_name)
        config.camera_index = int(os.getenv("CAMERA_INDEX", str(config.camera_index)))
        config.libcamera_device = os.getenv(
            "LIBCAMERA_DEVICE", config.libcamera_device
        )

        return config

    def _load_env_file(self, path: str):
        """Load environment variables from .env file."""
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Only set if not already in the environment
                    if key not in os.environ:
                        os.environ[key] = value

    def save(self, config_path: Optional[str] = None):
        """Save configuration to file."""
        if config_path is None:
            config_path = os.path.join(self.project_root, "config", "config.json")

        Path(config_path).parent.mkdir(parents=True, exist_ok=True)

        # Don't save API keys to file
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_api_key") and not k.endswith("_key")
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
