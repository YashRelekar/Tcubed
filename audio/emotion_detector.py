from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class EmotionResult:
    label: str
    confidence: float


def detect_emotion(audio: Optional[np.ndarray]) -> EmotionResult:
    if audio is None or audio.size == 0:
        return EmotionResult(label="neutral", confidence=0.0)

    rms = float(np.sqrt(np.mean(np.square(audio))))
    if rms < 0.02:
        return EmotionResult(label="calm", confidence=0.6)
    if rms > 0.08:
        return EmotionResult(label="excited", confidence=0.7)
    return EmotionResult(label="neutral", confidence=0.5)
