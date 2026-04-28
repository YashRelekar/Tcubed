# Raspberry Pi 5 Setup Guide

This guide covers everything needed to run **Jansky** on a Raspberry Pi 5 with:
- **reSpeaker XVF3800** 4-Mic Array (USB ID `2886:001a`)
- **Bluetooth A2DP speaker** (paired via PipeWire)
- **IMX219 MIPI camera** (Pi Camera Module v2 / v3)
- **Raspberry Pi OS Bookworm** (64-bit, `arm64`)

---

## Table of Contents

1. [Quick Start (Automated)](#1-quick-start-automated)
2. [Manual Installation](#2-manual-installation)
3. [Audio Configuration — XVF3800 Microphone](#3-audio-configuration--xvf3800-microphone)
4. [Bluetooth Speaker Setup](#4-bluetooth-speaker-setup)
5. [Camera Configuration — IMX219 MIPI](#5-camera-configuration--imx219-mipi)
6. [Hardware Configuration via Environment Variables](#6-hardware-configuration-via-environment-variables)
7. [Smoke Test](#7-smoke-test)
8. [Running Jansky](#8-running-jansky)
9. [Troubleshooting](#9-troubleshooting)
10. [arm64 / Bookworm Compatibility Notes](#10-arm64--bookworm-compatibility-notes)

---

## 1. Quick Start (Automated)

```bash
git clone https://github.com/YashRelekar/Tcubed.git
cd Tcubed/pibot_local_agent
chmod +x scripts/pi5_setup.sh
./scripts/pi5_setup.sh
```

The setup script handles:
- System packages (`apt`)
- Python virtual environment
- Python dependencies (`pip`)
- Ollama + Qwen 2.5:1.5b
- Whisper.cpp (built from source)
- Piper TTS British English voice

Then configure audio and Bluetooth:

```bash
./scripts/pi5_audio_config.sh
./scripts/pi5_bluetooth.sh
```

---

## 2. Manual Installation

### 2.1 System packages

```bash
sudo apt update && sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils \
  libcamera-apps \
  python3-libcamera \
  pipewire pipewire-pulse wireplumber \
  bluetooth bluez pulseaudio-module-bluetooth \
  sox
```

### 2.2 Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 2.3 Python dependencies

```bash
pip install \
  httpx \
  sounddevice \
  numpy \
  piper-tts \
  openwakeword \
  "onnxruntime>=1.16" \
  pygame \
  "opencv-python-headless"   # optional, for camera frame access
```

> **arm64 note**: All packages above have arm64/aarch64 wheels on PyPI.
> `onnxruntime>=1.16` ships native arm64 Linux wheels.
> `opencv-python-headless` avoids GTK/Qt dependencies and installs on Pi.

### 2.4 Ollama + Qwen 2.5:1.5b

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:1.5b
```

### 2.5 Whisper.cpp

```bash
git clone --depth=1 https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
cmake -B build -DWHISPER_BUILD_EXAMPLES=ON
cmake --build build --config Release -j$(nproc)
sudo cp build/bin/whisper-cli /usr/local/bin/whisper-cpp

# Download model
bash models/download-ggml-model.sh base.en

# Quantise (smaller + faster on Pi 5)
./build/bin/quantize models/ggml-base.en.bin models/ggml-base.en-q5_0.bin q5_0
cd ..
```

### 2.6 Piper TTS voice

```bash
mkdir -p piper/voices
wget -O piper/voices/en_GB-semaine-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
wget -O piper/voices/en_GB-semaine-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json
```

### 2.7 API keys (optional)

```bash
cp .env.example .env
nano .env   # add OPENWEATHER_API_KEY, NEWSAPI_KEY, MOONSHOT_API_KEY
```

---

## 3. Audio Configuration — XVF3800 Microphone

The **reSpeaker XVF3800** (USB ID `2886:001a`) is a 4-microphone array
that presents as a 48 kHz USB audio device.

### 3.1 Verify detection

```bash
lsusb | grep 2886
# Expected: Bus 003 Device 002: ID 2886:001a Seeed Technology Co., Ltd. reSpeaker XVF3800 4-Mic Array

arecord -l
# Should list a card with "XVF3800" in the name
```

### 3.2 Set as default capture device (PipeWire)

```bash
# List sources
pactl list short sources

# Find the XVF3800 source (name contains "xvf" or "respeaker")
pactl set-default-source <source-name>

# Make persistent
mkdir -p ~/.config/pipewire/pipewire-pulse.conf.d/
cat > ~/.config/pipewire/pipewire-pulse.conf.d/default-source.conf <<EOF
pulse.properties = {
    default.audio.source = <source-name>
}
EOF
```

### 3.3 Test recording

```bash
# Record 5 seconds at 48 kHz mono
arecord -D default -f S16_LE -r 48000 -c 1 -d 5 /tmp/test_mic.wav

# Play back
aplay /tmp/test_mic.wav
```

### 3.4 ALSA permissions

```bash
sudo usermod -aG audio $USER
# Log out and back in (or reboot)
```

### 3.5 Troubleshooting mic issues

| Problem | Fix |
|---|---|
| `arecord -l` shows no devices | Unplug/replug XVF3800; try different USB port |
| `ALSA lib: pcm.c: snd_pcm_open: No such file or directory` | Run `arecord -l` to find card name; set `MIC_NAME` in `.env` |
| Low/silent recording | Check `alsamixer` → select card → raise Capture level |
| `Permission denied` | `sudo usermod -aG audio $USER && sudo reboot` |
| XVF3800 shows multiple sub-devices | Use channel 0: `arecord -D plughw:XVF3800,0 ...` |

---

## 4. Bluetooth Speaker Setup

### 4.1 Automated setup

```bash
./scripts/pi5_bluetooth.sh
```

### 4.2 Manual pairing

```bash
# Start Bluetooth
sudo systemctl enable --now bluetooth

# Interactive pairing
bluetoothctl
# In the bluetoothctl shell:
power on
agent on
default-agent
scan on
# Wait for your speaker to appear
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
quit
```

### 4.3 Set as default PipeWire sink

```bash
pactl list short sinks   # find bluez sink name
pactl set-default-sink <bluez_sink_name>
```

### 4.4 Auto-reconnect on boot

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/bt-speaker.service <<EOF
[Unit]
Description=Reconnect Bluetooth speaker
After=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bluetoothctl connect AA:BB:CC:DD:EE:FF
RemainAfterExit=yes

[Install]
WantedBy=default.target
EOF

systemctl --user enable --now bt-speaker.service
```

### 4.5 Bluetooth troubleshooting

| Problem | Fix |
|---|---|
| `Failed to connect: org.bluez.Error.Failed` | Put speaker in pairing mode; retry `bluetoothctl connect <MAC>` |
| Speaker connects but no audio | `pactl list short sinks` → set the bluez sink as default |
| Audio cuts out | Disable WiFi 2.4 GHz or use 5 GHz (`sudo iwconfig wlan0 freq 5G`) |
| Disconnects after reboot | Enable bt-speaker.service (see above) |
| PipeWire doesn't see BT | `systemctl --user restart wireplumber` |

---

## 5. Camera Configuration — IMX219 MIPI

### 5.1 Enable camera

```bash
sudo raspi-config
# → Interface Options → Camera → Enable
sudo reboot
```

### 5.2 Verify detection (libcamera)

```bash
libcamera-hello --list-cameras
# Expected output includes: imx219

libcamera-hello --timeout 2000   # Preview for 2 seconds
```

### 5.3 Test still capture

```bash
libcamera-still \
  --output /tmp/test_capture.jpg \
  --timeout 3000 \
  --width 1280 --height 720 \
  --nopreview
```

### 5.4 Test from Python (libcamera-still backend)

```python
from senses.camera import Camera

cam = Camera(width=1280, height=720)
if cam.capture("/tmp/snapshot.jpg"):
    print("Snapshot saved!")
else:
    print("Capture failed")
```

### 5.5 Test from Python (OpenCV + GStreamer pipeline)

```python
from senses.camera import Camera
import cv2

cam = Camera()
frame = cam.capture_frame()   # returns BGR numpy array
if frame is not None:
    cv2.imwrite("/tmp/frame.jpg", frame)
```

### 5.6 Camera troubleshooting

| Problem | Fix |
|---|---|
| `libcamera-hello` hangs or no cameras | Check ribbon cable orientation; enable camera in raspi-config |
| `Camera not detected` | `dmesg | grep -i imx219`; try replugging ribbon |
| OpenCV `VideoCapture` fails | Install libcamera GStreamer plugin: `sudo apt install -y gstreamer1.0-libcamera` |
| Blurry image | Check lens focus ring (remove protective sticker) |

---

## 6. Hardware Configuration via Environment Variables

All hardware device selections are driven by environment variables.
No code changes needed to switch hardware.

Edit `.env` (copy from `.env.example`):

```bash
# Microphone device name substring (matches arecord -l output)
MIC_NAME=XVF3800

# Speaker device name substring (empty = system default / PipeWire BT)
SPEAKER_NAME=

# Camera index for OpenCV (0 = first camera)
CAMERA_INDEX=0

# libcamera device path (empty = auto)
LIBCAMERA_DEVICE=
```

Or set environment variables directly:

```bash
export MIC_NAME=XVF3800
export SPEAKER_NAME=
python orchestrator.py
```

To list available mic names:

```bash
arecord -l
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

---

## 7. Smoke Test

Run the automated health check:

```bash
source venv/bin/activate
chmod +x scripts/pi5_smoketest.sh
./scripts/pi5_smoketest.sh
```

This validates:
- ✅ Mic capture (XVF3800 detected, 2s WAV recorded)
- ✅ Speaker playback (test tone played)
- ✅ Camera capture (libcamera-still JPEG)
- ✅ Python imports (all modules)
- ✅ Piper TTS (synthesises speech)
- ✅ Whisper.cpp (binary + model operational)
- ✅ Ollama (running, `qwen2.5:1.5b` available)

Individual component tests:

```bash
source venv/bin/activate

# Test camera
python tests/test_camera.py

# Test audio pipeline (mic → STT → TTS → speaker)
python tests/test_audio_pipeline.py

# Test LLM router (requires Ollama)
python tests/test_router.py

# Test wake word detector
python tests/test_wake_word.py
```

---

## 8. Running Jansky

```bash
source venv/bin/activate

# Optional: run headless (no display)
# In config/config.json set "enable_ui": false

python orchestrator.py
```

Say **"Hey Jansky"** and start talking.

### Run as a systemd service (auto-start on boot)

```bash
cat > ~/.config/systemd/user/jansky.service <<EOF
[Unit]
Description=Jansky Voice Assistant
After=network.target bluetooth.target sound.target ollama.service

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/orchestrator.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user enable --now jansky.service
journalctl --user -f -u jansky.service   # follow logs
```

---

## 9. Troubleshooting

### Mic not found

```
RuntimeError: Audio device matching 'XVF3800' (input) not found
```

```bash
arecord -l                    # list ALSA devices
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

Update `MIC_NAME` in `.env` to match the name shown by the above commands.

### Speaker not found / ALSA error

```bash
aplay -l                      # list ALSA playback devices
pactl list short sinks        # list PipeWire/PulseAudio sinks
```

If using Bluetooth, leave `SPEAKER_NAME=` (empty) so `aplay` uses the
system default which PipeWire routes to the BT speaker.

### Whisper binary not found

```bash
which whisper-cpp             # should return /usr/local/bin/whisper-cpp
ls whisper.cpp/build/bin/     # check build output
```

Update `whisper_path` in `config/config.json` if installed elsewhere.

### Ollama not running

```bash
ollama serve &                # start in background
ollama list                   # check models
ollama pull qwen2.5:1.5b     # re-pull if missing
```

### No display / PyGame crash

Set `"enable_ui": false` in `config/config.json` to run headless.

### onnxruntime import error on arm64

```bash
pip install "onnxruntime>=1.16"   # native arm64 wheel
# OR install the system package:
sudo apt install -y python3-onnxruntime
```

### PipeWire issues

```bash
# Restart PipeWire stack
systemctl --user restart pipewire pipewire-pulse wireplumber
# Check status
systemctl --user status pipewire
```

---

## 10. arm64 / Bookworm Compatibility Notes

| Package | arm64 status | Notes |
|---|---|---|
| `onnxruntime` | ✅ Native wheel ≥1.16 | Use `pip install "onnxruntime>=1.16"` |
| `sounddevice` | ✅ Native wheel | PortAudio required (`portaudio19-dev`) |
| `piper-tts` | ✅ Native wheel | ONNX voice files work on arm64 |
| `openwakeword` | ✅ Native wheel | Bundled `hey_jarvis.onnx` works |
| `pygame` | ✅ Native wheel | SDL2 required (`libsdl2-dev`) |
| `opencv-python-headless` | ✅ arm64 wheel | GTK-free; works on Pi OS Bookworm |
| `numpy` | ✅ Native wheel | arm64 BLAS-accelerated |
| `httpx` | ✅ Pure Python | No native dependencies |
| Whisper.cpp | ✅ Builds from source | CMake ≥3.14; takes ~5 min on Pi 5 |
| Ollama | ✅ Official arm64 binary | Install via `install.sh` |

> **Python version**: The setup script uses the system Python 3 (Bookworm ships 3.11).
> Python 3.13 is not required; the original `venv313` name has been simplified to `venv`.
