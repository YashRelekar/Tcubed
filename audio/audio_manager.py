from __future__ import annotations

import logging
import queue
import time
import wave
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np
import pygame
import sounddevice as sd

from config import Config

PRE_ROLL_SECONDS = 0.5


class AudioManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._playback_initialized = False

    def record_until_silence(self) -> Optional[np.ndarray]:
        sample_rate = self.config.mic_sample_rate
        block_size = 1024
        max_seconds = self.config.max_record_seconds
        silence_threshold = self.config.silence_threshold
        silence_duration = self.config.silence_duration

        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        status_queue: queue.Queue[str] = queue.Queue()
        pre_roll = deque(maxlen=max(1, int(PRE_ROLL_SECONDS * sample_rate / block_size)))

        def callback(
            indata: np.ndarray,
            _frames: int,
            _time_info: dict[str, float],
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                status_queue.put(str(status))
            audio_queue.put(indata.copy())

        try:
            with sd.InputStream(
                channels=1,
                samplerate=sample_rate,
                blocksize=block_size,
                dtype="float32",
                callback=callback,
            ):
                self.logger.info("Listening for speech...")
                start_time = time.monotonic()
                speech_started = False
                silence_time = 0.0
                recorded_frames: list[np.ndarray] = []

                while True:
                    if not status_queue.empty():
                        self.logger.warning("Audio stream status: %s", status_queue.get())
                    try:
                        chunk = audio_queue.get(timeout=1)
                    except queue.Empty:
                        if time.monotonic() - start_time > max_seconds:
                            self.logger.warning("No audio detected within max duration.")
                            return None
                        continue

                    rms = float(np.sqrt(np.mean(np.square(chunk))))
                    chunk_duration = len(chunk) / sample_rate

                    if not speech_started:
                        pre_roll.append(chunk)
                        if rms > silence_threshold:
                            speech_started = True
                            recorded_frames.extend(list(pre_roll))
                            self.logger.info("Speech detected. Recording...")
                        elif time.monotonic() - start_time > max_seconds:
                            self.logger.warning("Speech not detected before timeout.")
                            return None

                    if speech_started:
                        recorded_frames.append(chunk)
                        if rms < silence_threshold:
                            silence_time += chunk_duration
                        else:
                            silence_time = 0.0

                        if silence_time >= silence_duration:
                            self.logger.info("Silence detected. Stopping recording.")
                            break

                        if time.monotonic() - start_time > max_seconds:
                            self.logger.warning("Reached max record duration.")
                            break

                audio = np.concatenate(recorded_frames, axis=0).reshape(-1)
                return audio
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.error("Failed to record audio: %s", exc)
            return None

    def write_wav(self, audio: np.ndarray, wav_path: Path) -> None:
        audio = np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767).astype(np.int16)
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.config.target_sample_rate)
            wav_file.writeframes(pcm.tobytes())

    def record_to_wav(self, wav_path: Path) -> bool:
        audio = self.record_until_silence()
        if audio is None:
            return False
        self.write_wav(audio, wav_path)
        return True

    def play_wav(self, wav_path: Path) -> None:
        try:
            if not self._playback_initialized:
                pygame.mixer.init(frequency=self.config.target_sample_rate, channels=1)
                self._playback_initialized = True
            pygame.mixer.music.load(str(wav_path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.error("Failed to play audio: %s", exc)

    def shutdown(self) -> None:
        if self._playback_initialized:
            pygame.mixer.quit()
            self._playback_initialized = False
