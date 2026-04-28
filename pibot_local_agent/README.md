# PiBot Local Agent (Jansky) — Raspberry Pi 5 Edition

A fully offline, wake-word-activated voice assistant that runs on a **Raspberry Pi 5**.
Simple queries are handled locally by a 1.5 B parameter LLM; complex questions are
handed off to a cloud model.

This is a port of [`mayukh4/pibot_local_agent`](https://github.com/mayukh4/pibot_local_agent)
into the Tcubed monorepo, with full support for:

| Hardware | Details |
|---|---|
| **Microphone** | reSpeaker XVF3800 4-Mic Array (USB `2886:001a`) |
| **Speaker** | Bluetooth A2DP speaker via PipeWire |
| **Camera** | IMX219 MIPI (Pi Camera Module v2/v3) via libcamera |
| **OS** | Raspberry Pi OS Bookworm, 64-bit (`arm64`) |

Named after [Karl Jansky](https://en.wikipedia.org/wiki/Karl_Guthe_Jansky), the pioneer of radio astronomy.

---

## Quick Start (Raspberry Pi 5)

```bash
# From the Tcubed repo root:
cd pibot_local_agent

chmod +x scripts/pi5_setup.sh
./scripts/pi5_setup.sh          # installs everything

./scripts/pi5_audio_config.sh   # configure XVF3800 mic
./scripts/pi5_bluetooth.sh      # pair Bluetooth speaker

# Run smoke test
source venv/bin/activate
./scripts/pi5_smoketest.sh

# Start the assistant
python orchestrator.py
```

Say **"Hey Jansky"** and start talking.

---

## Hardware Configuration

All hardware selections are driven by environment variables — no code changes needed.

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
nano .env
```

| Variable | Default | Description |
|---|---|---|
| `MIC_NAME` | `XVF3800` | Substring of mic device name (`arecord -l`) |
| `SPEAKER_NAME` | *(empty)* | Substring of speaker name; empty = system default (BT via PipeWire) |
| `CAMERA_INDEX` | `0` | OpenCV camera index (0 = IMX219 on Pi 5) |
| `LIBCAMERA_DEVICE` | *(empty)* | libcamera device path; empty = auto-select |
| `OPENWEATHER_API_KEY` | | Live weather lookups |
| `NEWSAPI_KEY` | | Top news headlines |
| `MOONSHOT_API_KEY` | | Cloud AI answers (Kimi K2) |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RASPBERRY PI 5                           │
│                                                                 │
│  ┌──────────────────┐  "Hey Jansky"  ┌──────────────────────┐  │
│  │ XVF3800 4-Mic    │ ─────────────► │  Wake Word Detector  │  │
│  │ Array (48 kHz)   │                │  (openWakeWord+ONNX) │  │
│  └──────────────────┘                └──────────┬───────────┘  │
│                                                  │ wake!        │
│                                                  ▼             │
│                                      ┌──────────────────────┐  │
│                                      │  Audio Manager       │  │
│                                      │  Record → silence    │  │
│                                      └──────────┬───────────┘  │
│                                                  │ raw audio    │
│                                                  ▼             │
│                                      ┌──────────────────────┐  │
│                                      │  Whisper.cpp (STT)   │  │
│                                      │  48kHz→16kHz→text    │  │
│                                      └──────────┬───────────┘  │
│                                                  │ text         │
│                                                  ▼             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  LLM Router (Ollama)                     │  │
│  │               Qwen 2.5 · 1.5 B                          │  │
│  │  Simple chat ──► respond directly                       │  │
│  │  Time/Date   ──► time_tool        (local)               │  │
│  │  Weather     ──► weather_tool     (OpenWeatherMap)      │  │
│  │  News        ──► news_tool        (NewsAPI)             │  │
│  │  System      ──► system_tool      (CPU/RAM/uptime)      │  │
│  │  Complex     ──► cloud_handoff    (Kimi K2 / Moonshot)  │  │
│  └─────────────────────────────────┬────────────────────────┘  │
│                                     │ response text             │
│                                     ▼                          │
│                         ┌────────────────────┐                 │
│                         │  Piper TTS         │                 │
│                         │  text → WAV        │                 │
│                         └────────┬───────────┘                 │
│                                  │                             │
│            ┌─────────────────────┼──────────────────────┐     │
│            ▼                                             ▼     │
│   ┌─────────────────┐                        ┌──────────────┐  │
│   │  BT Speaker     │                        │  PyGame Face │  │
│   │  (PipeWire A2DP)│                        │  (800×480)   │  │
│   └─────────────────┘                        └──────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  IMX219 MIPI Camera (libcamera / OpenCV)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
pibot_local_agent/
├── orchestrator.py              # Main entry point
├── config.py                    # Config dataclass — loads .env, config.json, env vars
├── setup.sh                     # One-command install (delegates to scripts/pi5_setup.sh)
├── .env.example                 # Template for API keys + hardware config
│
├── audio/
│   ├── audio_manager.py         # Mic recording (silence detection) + speaker playback
│   ├── tts_engine.py            # Piper TTS wrapper (text → WAV)
│   └── stt_engine.py            # Whisper.cpp wrapper (audio → text)
│
├── brain/
│   ├── router.py                # Intent routing — keyword + LLM tool-calling
│   ├── ollama_client.py         # Ollama HTTP client
│   ├── cloud_client.py          # Kimi K2 / Moonshot HTTP client
│   ├── tool_definitions.py      # Tool schemas + system prompt
│   └── tools/
│       ├── time_tool.py         # Current time & date
│       ├── weather_tool.py      # OpenWeatherMap
│       ├── news_tool.py         # NewsAPI headlines
│       ├── system_tool.py       # CPU temp, RAM, uptime, disk
│       └── joke_tool.py         # Random joke API
│
├── senses/
│   ├── wake_word_detector.py    # openWakeWord listener (threaded)
│   └── camera.py                # IMX219 camera (libcamera + OpenCV)
│
├── ui/
│   └── ui_manager.py            # PyGame animated face
│
├── config/
│   ├── config.json              # Runtime config (Pi 5 defaults)
│   ├── local_soul.md            # Personality prompt for local LLM
│   └── cloud_soul.md            # Personality prompt for cloud LLM
│
├── scripts/
│   ├── pi5_setup.sh             # Full Pi 5 install script
│   ├── pi5_audio_config.sh      # XVF3800 mic + speaker configuration
│   ├── pi5_bluetooth.sh         # Bluetooth speaker pairing + persistence
│   └── pi5_smoketest.sh         # End-to-end health check
│
├── docs/
│   └── pi5_setup.md             # Comprehensive Pi 5 setup guide
│
├── tests/
│   ├── test_router.py           # LLM router tests
│   ├── test_wake_word.py        # Wake word detector test
│   ├── test_audio_pipeline.py   # TTS + STT pipeline test
│   └── test_camera.py           # IMX219 camera capture test
│
├── assets/
│   ├── face/                    # PNG face expressions for UI
│   └── fillers/                 # Pre-generated filler WAVs
│
├── models/wake_word/            # openWakeWord ONNX model
└── piper/voices/                # Piper TTS voice files (downloaded by setup)
```

---

## Features

| Feature | How it works | API key needed? |
|---|---|---|
| **Wake word** | openWakeWord ONNX model (hey_jarvis built-in) | No |
| **Local chat** | Qwen 2.5:1.5b via Ollama | No |
| **Time & date** | Python `datetime` | No |
| **System status** | Reads `/proc` and `/sys` | No |
| **Jokes** | Official Joke API (free) | No |
| **Weather** | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| **News headlines** | NewsAPI | `NEWSAPI_KEY` |
| **Cloud AI** | Kimi K2 (Moonshot) | `MOONSHOT_API_KEY` |
| **Animated UI** | PyGame on Wayland | No |
| **Speech** | Piper TTS (British English) | No |
| **Speech recognition** | Whisper.cpp (quantised) | No |
| **Camera** | libcamera / OpenCV (IMX219) | No |

---

## Configuration

Key settings in `config/config.json`:

| Setting | Default | Description |
|---|---|---|
| `chat_model` | `qwen2.5:1.5b` | Ollama model |
| `wake_word_threshold` | `0.5` | Wake word confidence (0–1) |
| `mic_sample_rate` | `48000` | XVF3800 native sample rate |
| `mic_name` | `XVF3800` | Mic device name substring |
| `speaker_name` | `""` | Speaker name; empty = system default |
| `camera_index` | `0` | OpenCV camera index |
| `enable_ui` | `false` | Set `true` for PyGame display |
| `local_location` | `Kingston, CA` | Default city for weather |

All settings can also be overridden via environment variables — see `.env.example`.

---

## Testing

```bash
source venv/bin/activate

# Smoke test (recommended first)
./scripts/pi5_smoketest.sh

# Individual tests
python tests/test_camera.py
python tests/test_audio_pipeline.py
python tests/test_router.py
python tests/test_wake_word.py
```

---

## Troubleshooting

See [docs/pi5_setup.md](docs/pi5_setup.md) for the full troubleshooting guide.

| Problem | Fix |
|---|---|
| `Mic 'XVF3800' not found` | Check `arecord -l`; update `MIC_NAME` in `.env` |
| Speaker silent | `pactl list short sinks`; check BT connection |
| Camera fails | Enable in `raspi-config`; run `libcamera-hello --list-cameras` |
| Whisper not found | Run `./scripts/pi5_setup.sh` or set `whisper_path` in `config.json` |
| Ollama not running | Run `ollama serve` |
| PyGame crash | Set `"enable_ui": false` in `config/config.json` |
| `onnxruntime` error | `pip install "onnxruntime>=1.16"` |

---

## License

MIT — see upstream [`mayukh4/pibot_local_agent`](https://github.com/mayukh4/pibot_local_agent)
