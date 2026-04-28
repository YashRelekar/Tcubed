#!/usr/bin/env bash
# ==============================================================
#  Jansky on Raspberry Pi 5 — One-Command Installer
# ==============================================================
#  Tested on: Raspberry Pi OS Bookworm (64-bit, arm64)
#  Hardware:
#    Microphone : reSpeaker XVF3800 (USB 2886:001a)
#    Speaker    : Bluetooth A2DP via PipeWire
#    Camera     : IMX219 MIPI (8 MP, Pi Camera Module v2)
#    Compute    : Raspberry Pi 5
#
#  Usage:
#    chmod +x scripts/pi5_setup.sh
#    ./scripts/pi5_setup.sh
#
#  What this script does (in order):
#   1. Installs system packages (apt)
#   2. Creates a Python 3 virtual environment
#   3. Installs Python dependencies (pip)
#   4. Installs Ollama and pulls Qwen 2.5:1.5b
#   5. Builds Whisper.cpp from source and downloads the model
#   6. Downloads the Piper TTS voice
#   7. Creates .env from template
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_DIR"

# ── colours ───────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Jansky — Raspberry Pi 5 Setup                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Arch check ───────────────────────────────────────────────
ARCH="$(uname -m)"
info "Architecture: ${ARCH}"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  echo -e "${YELLOW}Warning: This script is designed for arm64 (Pi 5). Continuing anyway.${NC}"
fi

# ── 1. System packages ────────────────────────────────────────
info "Installing system packages …"
sudo apt update -qq
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils \
  libcamera-apps \
  python3-libcamera \
  pipewire pipewire-pulse wireplumber \
  bluetooth bluez pulseaudio-module-bluetooth \
  bluez-tools
ok "System packages installed"

# ── 2. Python virtual environment ─────────────────────────────
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
  info "Creating Python virtual environment …"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
ok "Virtual environment ready (${VENV_DIR})"

# ── 3. Python dependencies ────────────────────────────────────
info "Installing Python packages …"

# Core packages — arm64-compatible wheels available on PyPI
pip install -q \
  httpx \
  sounddevice \
  numpy \
  piper-tts \
  openwakeword \
  pygame

# onnxruntime: use the arm64 build from PyPI (available since 1.16)
# On Pi 5 (Bookworm) the system Python ships libonnxruntime; using the pip
# package avoids a libc version mismatch.
pip install -q "onnxruntime>=1.16"

# Optional: OpenCV for camera programmatic access
# The headless build avoids pulling in GTK/Qt which are slow to install.
pip install -q "opencv-python-headless" || \
  echo "  (opencv-python-headless unavailable — camera will use libcamera-still)"

ok "Python packages installed"

# ── 4. Ollama + model ─────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  info "Installing Ollama …"
  curl -fsSL https://ollama.com/install.sh | sh
fi
ok "Ollama installed"

info "Pulling Qwen 2.5:1.5b (this may take a few minutes) …"
ollama pull qwen2.5:1.5b
ok "Qwen 2.5:1.5b ready"

# ── 5. Whisper.cpp ────────────────────────────────────────────
WHISPER_BIN="/usr/local/bin/whisper-cpp"
if [ ! -f "$WHISPER_BIN" ]; then
  if [ ! -d "whisper.cpp" ]; then
    info "Cloning Whisper.cpp …"
    git clone --depth=1 https://github.com/ggerganov/whisper.cpp.git
  fi
  info "Building Whisper.cpp (this takes ~5–10 min on Pi 5) …"
  cd whisper.cpp
  cmake -B build -DWHISPER_BUILD_EXAMPLES=ON
  cmake --build build --config Release -j"$(nproc)"
  sudo cp build/bin/whisper-cli "$WHISPER_BIN"
  ok "Whisper.cpp built → ${WHISPER_BIN}"

  info "Downloading Whisper base.en model …"
  bash models/download-ggml-model.sh base.en
  if [ -f build/bin/quantize ]; then
    ./build/bin/quantize \
      models/ggml-base.en.bin \
      models/ggml-base.en-q5_0.bin \
      q5_0
    ok "Whisper model quantised (q5_0)"
  fi
  cd "$PROJECT_DIR"
else
  ok "Whisper.cpp already installed at ${WHISPER_BIN}"
fi

# ── 6. Piper TTS voice ────────────────────────────────────────
VOICE_DIR="piper/voices"
VOICE_FILE="${VOICE_DIR}/en_GB-semaine-medium.onnx"
if [ ! -f "$VOICE_FILE" ]; then
  info "Downloading Piper TTS voice …"
  mkdir -p "$VOICE_DIR"
  wget -q --show-progress -O "$VOICE_FILE" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx"
  wget -q -O "${VOICE_FILE}.json" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json"
  ok "Piper voice downloaded"
else
  ok "Piper voice already present"
fi

# ── 7. .env file ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  info "Created .env from template — edit it to add your API keys"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Jansky is installed!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo ""
echo "  Next steps:"
echo "    1. Configure audio / Bluetooth:"
echo "         ./scripts/pi5_audio_config.sh"
echo "         ./scripts/pi5_bluetooth.sh"
echo "    2. (Optional) Add API keys:"
echo "         nano .env"
echo "    3. Run smoke test:"
echo "         ./scripts/pi5_smoketest.sh"
echo "    4. Start Jansky:"
echo "         source venv/bin/activate"
echo "         python orchestrator.py"
echo ""
echo "  Say \"Hey Jansky\" and start talking!"
echo ""
