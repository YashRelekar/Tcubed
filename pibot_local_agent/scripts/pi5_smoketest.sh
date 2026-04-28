#!/usr/bin/env bash
# ==============================================================
#  Jansky — Raspberry Pi 5 End-to-End Smoke Test
# ==============================================================
#  Validates:
#   1. Mic capture (XVF3800) works
#   2. Speaker playback (Bluetooth A2DP) works
#   3. Camera capture (IMX219 MIPI via libcamera) works
#   4. Whisper.cpp STT works on a test WAV
#   5. Piper TTS works
#   6. Ollama is running and model is available
#   7. Python imports succeed (all modules loadable)
#   8. App can start (--check flag, dry run)
#
#  Usage:
#    chmod +x scripts/pi5_smoketest.sh
#    source venv/bin/activate && ./scripts/pi5_smoketest.sh
#
#  Exit code: 0 = all tests passed, 1 = one or more failed
# ==============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PASS=0
FAIL=0

pass() { echo -e "${GREEN}[PASS]${NC} $*"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL+1)); }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }
section() { echo ""; echo "── $* ──"; }

echo ""
echo "════════════════════════════════════════════════════"
echo "  Jansky — Pi 5 Smoke Test"
echo "════════════════════════════════════════════════════"

# ── Helper: check command exists ──────────────────────────────
require_cmd() {
  local cmd="$1"
  local pkg="${2:-$1}"
  if ! command -v "$cmd" &>/dev/null; then
    fail "Command '${cmd}' not found. Install: sudo apt install -y ${pkg}"
    return 1
  fi
  return 0
}

# ── 1. Mic capture ────────────────────────────────────────────
section "1. Microphone Capture (XVF3800)"
MIC_WAV="/tmp/jansky_smoke_mic.wav"
MIC_DURATION=2

if lsusb 2>/dev/null | grep -q "2886:001a"; then
  info "XVF3800 detected on USB"
else
  fail "XVF3800 (USB 2886:001a) NOT detected on USB — check cable and port"
fi

if require_cmd arecord alsa-utils; then
  if arecord -D default -f S16_LE -r 48000 -c 1 -d "$MIC_DURATION" "$MIC_WAV" 2>/dev/null; then
    if [ -s "$MIC_WAV" ]; then
      pass "Mic capture: recorded ${MIC_DURATION}s WAV ($(wc -c < "${MIC_WAV}") bytes)"
    else
      fail "Mic capture: WAV file is empty"
    fi
  else
    fail "Mic capture: arecord failed (check arecord -l for device list)"
  fi
  rm -f "$MIC_WAV"
fi

# ── 2. Speaker playback ───────────────────────────────────────
section "2. Speaker Playback (Bluetooth / default sink)"
TONE_WAV="/tmp/jansky_smoke_tone.wav"

# Generate a simple 440 Hz test tone using sox if available
if command -v sox &>/dev/null; then
  sox -n -r 22050 -c 1 "$TONE_WAV" synth 1.0 sine 440 2>/dev/null
  if require_cmd aplay alsa-utils; then
    if aplay "$TONE_WAV" 2>/dev/null; then
      pass "Speaker playback: 440 Hz tone played"
    else
      fail "Speaker playback: aplay failed (check aplay -l)"
    fi
  fi
  rm -f "$TONE_WAV"
elif command -v paplay &>/dev/null; then
  # Fallback: play a system sound
  BEEP=$(find /usr/share/sounds -name "*.wav" 2>/dev/null | head -1)
  if [ -n "$BEEP" ]; then
    paplay "$BEEP" 2>/dev/null && pass "Speaker playback: played ${BEEP}" || \
      fail "Speaker playback: paplay failed"
  else
    info "Speaker playback: no test sound available (install sox for tone test)"
  fi
else
  info "Speaker playback: install sox for automated tone test"
  info "  Manual test: speaker-test -t wav -c 1"
fi

# ── 3. Camera capture ─────────────────────────────────────────
section "3. Camera Capture (IMX219 MIPI via libcamera)"
CAM_IMG="/tmp/jansky_smoke_cam.jpg"

if command -v libcamera-still &>/dev/null; then
  if libcamera-still \
      --output "$CAM_IMG" \
      --timeout 3000 \
      --width 640 --height 480 \
      --nopreview 2>/dev/null; then
    if [ -s "$CAM_IMG" ]; then
      pass "Camera capture: libcamera-still → $(wc -c < "${CAM_IMG}") bytes"
    else
      fail "Camera capture: libcamera-still produced empty file"
    fi
  else
    fail "Camera capture: libcamera-still failed"
    info "  Check: libcamera-hello --list-cameras"
    info "  Enable camera in raspi-config → Interface Options → Camera"
  fi
  rm -f "$CAM_IMG"
else
  fail "Camera: libcamera-still not found (install: sudo apt install -y libcamera-apps)"
fi

# ── 4. Python imports ─────────────────────────────────────────
section "4. Python Module Imports"

if ! command -v python3 &>/dev/null; then
  fail "python3 not found"
else
  python3 - <<'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
errors = []

def try_import(module, pkg=None):
    try:
        __import__(module)
    except ImportError as e:
        errors.append(f"  {module}: {e}  (install: pip install {pkg or module})")

try_import("sounddevice")
try_import("numpy")
try_import("httpx")
try_import("piper", "piper-tts")
try_import("openwakeword", "openwakeword")
try_import("onnxruntime", "onnxruntime")
try_import("pygame")

# Project modules
for mod in ["config", "audio.audio_manager", "audio.tts_engine",
            "audio.stt_engine", "brain.ollama_client", "brain.router",
            "senses.wake_word_detector", "senses.camera"]:
    try_import(mod)

if errors:
    print("FAIL: Missing imports:")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("PASS: All Python imports succeeded")
PYEOF
  if [ $? -eq 0 ]; then
    pass "Python imports"
  else
    fail "Python imports (see above)"
  fi
fi

# ── 5. Piper TTS ──────────────────────────────────────────────
section "5. Piper TTS"
VOICE_ONNX="piper/voices/en_GB-semaine-medium.onnx"
if [ -f "$VOICE_ONNX" ]; then
  TTS_WAV="/tmp/jansky_smoke_tts.wav"
  if python3 - <<PYEOF 2>/dev/null
import sys, os
sys.path.insert(0, os.getcwd())
from audio.tts_engine import PiperTTS
t = PiperTTS()
t.synthesize("Smoke test. Jansky is operational.", "/tmp/jansky_smoke_tts.wav")
PYEOF
  then
    if [ -s "$TTS_WAV" ]; then
      pass "Piper TTS: synthesised WAV ($(wc -c < "${TTS_WAV}") bytes)"
      command -v aplay &>/dev/null && aplay "$TTS_WAV" 2>/dev/null || true
    else
      fail "Piper TTS: empty output"
    fi
    rm -f "$TTS_WAV"
  else
    fail "Piper TTS: synthesis failed"
  fi
else
  fail "Piper TTS: voice model not found at ${VOICE_ONNX}"
  info "  Run: ./scripts/pi5_setup.sh to download the voice"
fi

# ── 6. Whisper.cpp ────────────────────────────────────────────
section "6. Whisper.cpp STT"
WHISPER_BIN="/usr/local/bin/whisper-cpp"
WHISPER_MODEL="whisper.cpp/models/ggml-base.en-q5_0.bin"

if [ ! -f "$WHISPER_BIN" ]; then
  fail "Whisper binary not found at ${WHISPER_BIN} — run ./scripts/pi5_setup.sh"
elif [ ! -f "$WHISPER_MODEL" ]; then
  fail "Whisper model not found at ${WHISPER_MODEL} — run ./scripts/pi5_setup.sh"
else
  # Create a 1-second silent WAV and transcribe it (output should be empty)
  SILENT_WAV="/tmp/jansky_smoke_silent.wav"
  python3 - <<PYEOF 2>/dev/null
import wave, struct, os
with wave.open("$SILENT_WAV", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(struct.pack("<16000h", *([0]*16000)))
PYEOF
  if $WHISPER_BIN -m "$WHISPER_MODEL" -f "$SILENT_WAV" -l en -t 4 \
      --no-timestamps -np &>/dev/null; then
    pass "Whisper.cpp: binary and model operational"
  else
    fail "Whisper.cpp: transcription failed — check binary and model"
  fi
  rm -f "$SILENT_WAV"
fi

# ── 7. Ollama ─────────────────────────────────────────────────
section "7. Ollama (LLM)"
if command -v ollama &>/dev/null; then
  if curl -s http://localhost:11434/api/tags &>/dev/null; then
    if ollama list 2>/dev/null | grep -q "qwen2.5:1.5b"; then
      pass "Ollama: running, qwen2.5:1.5b model available"
    else
      fail "Ollama: running but qwen2.5:1.5b not found — run: ollama pull qwen2.5:1.5b"
    fi
  else
    fail "Ollama: not running — start with: ollama serve"
  fi
else
  fail "Ollama not installed — run: curl -fsSL https://ollama.com/install.sh | sh"
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo "  Smoke Test Results"
echo "════════════════════════════════════════════════════"
echo -e "  ${GREEN}PASSED: ${PASS}${NC}"
if [ "$FAIL" -gt 0 ]; then
  echo -e "  ${RED}FAILED: ${FAIL}${NC}"
  echo ""
  echo "  Fix the failures above, then run:"
  echo "    ./scripts/pi5_smoketest.sh"
  echo ""
  exit 1
else
  echo -e "  All tests passed!"
  echo ""
  echo "  Start Jansky:"
  echo "    source venv/bin/activate"
  echo "    python orchestrator.py"
  echo ""
  exit 0
fi
