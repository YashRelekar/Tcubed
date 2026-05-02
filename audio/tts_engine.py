from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Optional

from piper.config import SynthesisConfig
from piper.voice import PiperVoice

from config import Config


class PiperTTSEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.voice = PiperVoice.load(
            config.piper_voice,
            config_path=config.piper_voice_config,
            use_cuda=False,
        )

    def synthesize_to_file(self, text: str, wav_path: Path, rate: Optional[float] = None) -> None:
        if not text.strip():
            return
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        rate = rate or self.config.tts_rate
        if not rate or rate <= 0:
            rate = 1.0
        syn_config = SynthesisConfig(length_scale=1.0 / rate)
        with wave.open(str(wav_path), "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
