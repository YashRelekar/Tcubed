"""
Audio Manager - Handles microphone input and speaker output.

Pi 5 / XVF3800 notes
--------------------
* The reSpeaker XVF3800 (USB ID 2886:001a) presents as a 48 kHz 4-channel
  capture device.  We record from channel 0 and decimate 3:1 to 16 kHz.
* For playback we prefer ALSA `aplay`; when a Bluetooth A2DP speaker is
  the system default (via PipeWire), leaving SPEAKER_NAME empty causes
  `aplay` to use the default sink automatically.
* Device name substrings are resolved from env vars MIC_NAME / SPEAKER_NAME
  at runtime so no code changes are needed to switch hardware.
"""

import os
import re
import sounddevice as sd
import numpy as np
import wave
import subprocess
from threading import Lock
from typing import Optional


# ---------------------------------------------------------------------------
# Device helpers
# ---------------------------------------------------------------------------

def _find_device_by_name(name_substring: str, kind: str) -> int:
    """Find a sounddevice device index by name substring.

    Args:
        name_substring: Partial device name to match.
        kind: "input" or "output".

    Returns:
        Device index, or raises RuntimeError if not found.
    """
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if name_substring.lower() in d["name"].lower() and d[channel_key] > 0:
            return i
    raise RuntimeError(
        "Audio device matching '{}' ({}) not found. "
        "Available: {}".format(
            name_substring, kind,
            [(i, d["name"]) for i, d in enumerate(devices)]
        )
    )


def _find_alsa_card_by_name(name_substring: str) -> Optional[str]:
    """Find ALSA playback card by name; return 'plughw:N,0' or None.

    Returning None means 'use the system default', which is correct for
    PipeWire-managed Bluetooth sinks.
    """
    if not name_substring:
        return None  # Use system default (PipeWire / BT speaker)
    try:
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("card ") and name_substring.lower() in line.lower():
                card_num = line.split(":")[0].replace("card ", "").strip()
                return "plughw:{},0".format(card_num)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Default device name substrings (overridden by env vars / Config)
# ---------------------------------------------------------------------------

# reSpeaker XVF3800 4-Mic Array shows up as "XVF3800" in `arecord -l`
_DEFAULT_MIC_NAME = os.getenv("MIC_NAME", "XVF3800")
# Empty string → use system default playback device (PipeWire / BT A2DP)
_DEFAULT_SPEAKER_NAME = os.getenv("SPEAKER_NAME", "")


class AudioManager:
    """Manages microphone input and speaker output."""

    def __init__(
        self,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        channels: int = 1,
        dtype: str = 'int16',
        mic_name: Optional[str] = None,
        speaker_name: Optional[str] = None,
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.channels = channels
        self.dtype = dtype
        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

        mic_name = mic_name if mic_name is not None else _DEFAULT_MIC_NAME
        speaker_name = speaker_name if speaker_name is not None else _DEFAULT_SPEAKER_NAME

        # Resolve mic device index by name substring
        self.mic_device = _find_device_by_name(mic_name, "input")
        # Resolve speaker ALSA device string (None = system default)
        self.speaker_alsa = _find_alsa_card_by_name(speaker_name)

        print("    Mic device index: {} (matched '{}')".format(self.mic_device, mic_name))
        if self.speaker_alsa:
            print("    Speaker ALSA: {} (matched '{}')".format(self.speaker_alsa, speaker_name))
        else:
            print("    Speaker: system default (PipeWire / Bluetooth A2DP)")

    # ------------------------------------------------------------------
    # Muting
    # ------------------------------------------------------------------

    def mute(self):
        """Mute microphone input (during TTS playback)."""
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        """Unmute microphone input."""
        with self._mute_lock:
            self.is_muted = False

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _normalize(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        """Apply gain normalization for weak USB mics."""
        peak = np.max(np.abs(audio.astype(np.float64)))
        if peak < 50:
            return audio
        gain = (target_peak * 32767) / peak
        return np.clip(audio.astype(np.float64) * gain, -32768, 32767).astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        max_duration: float = 30.0
    ) -> Optional[np.ndarray]:
        """
        Record audio until silence is detected.

        Records at mic_sample_rate (default 48 kHz for XVF3800), then
        decimates by an integer factor down to target_sample_rate (16 kHz).
        """
        if self.is_muted:
            return None

        self._audio_buffer = []
        self._recording = True
        silence_samples = 0
        silence_samples_needed = int(silence_duration * self.mic_sample_rate / 4096)
        max_samples = int(max_duration * self.mic_sample_rate / 4096)
        total_samples = 0

        def callback(indata, frames, time, status):
            if self.is_muted or not self._recording:
                return
            self._audio_buffer.append(indata.copy())

        stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.mic_sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=4096,
            latency="high",
            callback=callback
        )
        stream.start()

        try:
            while self._recording and total_samples < max_samples:
                sd.sleep(100)
                total_samples += 1

                if len(self._audio_buffer) > 0:
                    recent = self._audio_buffer[-1]
                    rms = np.sqrt(np.mean(recent.astype(np.float32) ** 2)) / 32768
                    if rms < silence_threshold:
                        silence_samples += 1
                        if silence_samples >= silence_samples_needed:
                            break
                    else:
                        silence_samples = 0
        finally:
            stream.stop()
            stream.close()

        self._recording = False

        if len(self._audio_buffer) == 0:
            return None

        raw_audio = np.concatenate(self._audio_buffer, axis=0).flatten()
        normalized = self._normalize(raw_audio)

        # Decimate from mic_sample_rate to target sample_rate.
        # For 48kHz → 16kHz the factor is exactly 3.
        decimate_factor = self.mic_sample_rate // self.sample_rate
        if decimate_factor < 1:
            decimate_factor = 1
        decimated = normalized[::decimate_factor]
        return decimated

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        """Save audio array to WAV file."""
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def play_wav(self, filepath: str):
        """Play a WAV file through speakers."""
        self.mute()
        try:
            cmd = ["aplay"]
            if self.speaker_alsa:
                cmd += ["-D", self.speaker_alsa]
            cmd.append(filepath)
            subprocess.run(cmd, check=True, capture_output=True)
        except FileNotFoundError:
            # aplay not available — fall back to sounddevice
            import wave as wav_mod
            with wav_mod.open(filepath, 'rb') as wf:
                audio_data = np.frombuffer(
                    wf.readframes(wf.getnframes()),
                    dtype=np.int16
                )
                sd.play(audio_data, wf.getframerate())
                sd.wait()
        except Exception as e:
            print("Playback error: {}".format(e))
        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        """Play audio array through speakers."""
        self.mute()
        try:
            sd.play(audio, self.sample_rate)
            sd.wait()
        finally:
            self.unmute()
