from __future__ import annotations

import logging
import signal
import threading
import uuid

from audio.audio_manager import AudioManager
from audio.emotion_detector import detect_emotion
from audio.stt_engine import WhisperCppSTT
from audio.tts_engine import PiperTTSEngine
from brain.ollama_client import OllamaClient
from brain.router import ConversationRouter
from brain.session_manager import SessionManager
from brain.tool_definitions import get_tool_definitions, get_tool_handlers
from config import Config


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> None:
    config = Config.load()
    _setup_logging(config.log_level)

    logger = logging.getLogger("jarvis")
    stop_event = threading.Event()

    def _signal_handler(signum, frame) -> None:  # type: ignore[override]
        logger.info("Received signal %s. Shutting down...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    session_manager = SessionManager(config)
    audio_manager = AudioManager(config)
    stt_engine = WhisperCppSTT(config)
    tts_engine = PiperTTSEngine(config)
    ollama_client = OllamaClient(config)
    router = ConversationRouter(
        config,
        ollama_client,
        get_tool_definitions(),
        get_tool_handlers(),
        session_manager,
    )

    logger.info("%s is online.", config.assistant_name)

    try:
        while not stop_event.is_set():
            audio = audio_manager.record_until_silence()
            if audio is None:
                continue

            emotion = detect_emotion(audio)
            input_wav = config.audio_temp_dir / f"input_{uuid.uuid4().hex}.wav"
            audio_manager.write_wav(audio, input_wav)

            try:
                transcript = stt_engine.transcribe(input_wav)
            except Exception as exc:
                logger.error("STT failed: %s", exc)
                input_wav.unlink(missing_ok=True)
                continue
            finally:
                input_wav.unlink(missing_ok=True)

            if not transcript:
                logger.info("Empty transcript. Listening again...")
                continue

            logger.info("User said: %s", transcript)
            response = router.handle(transcript, emotion)
            if not response:
                logger.info("No response generated.")
                continue

            logger.info("%s: %s", config.assistant_name, response)
            output_wav = config.audio_temp_dir / f"tts_{uuid.uuid4().hex}.wav"
            try:
                tts_engine.synthesize_to_file(response, output_wav)
                audio_manager.play_wav(output_wav)
            except Exception as exc:  # pragma: no cover - hardware dependent
                logger.error("TTS failed: %s", exc)
            finally:
                output_wav.unlink(missing_ok=True)
    finally:
        ollama_client.close()
        audio_manager.shutdown()


if __name__ == "__main__":
    main()
