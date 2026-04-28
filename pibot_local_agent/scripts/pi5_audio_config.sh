#!/usr/bin/env bash
# ==============================================================
#  Audio Configuration for Raspberry Pi 5
#  reSpeaker XVF3800 mic + Bluetooth A2DP speaker
# ==============================================================
#  This script:
#   1. Shows current audio devices (ALSA)
#   2. Verifies the XVF3800 mic is detected
#   3. Explains how to set PipeWire / PulseAudio defaults
#   4. Tests mic recording and plays back the recording
#
#  Usage:
#    chmod +x scripts/pi5_audio_config.sh
#    ./scripts/pi5_audio_config.sh
# ==============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; }

RECORD_DURATION=5        # seconds for the test recording
TEST_WAV="/tmp/jansky_mic_test.wav"

echo ""
echo "════════════════════════════════════════════════════"
echo "  Jansky — Audio Device Configuration"
echo "════════════════════════════════════════════════════"
echo ""

# ── List ALSA capture devices ─────────────────────────────────
info "ALSA capture devices (microphones):"
if arecord -l 2>/dev/null; then
  echo ""
else
  warn "arecord not found — install alsa-utils: sudo apt install -y alsa-utils"
fi

# ── Check for XVF3800 ─────────────────────────────────────────
info "Looking for reSpeaker XVF3800 (USB ID 2886:001a) …"
if lsusb | grep -q "2886:001a"; then
  ok "reSpeaker XVF3800 detected on USB"
else
  warn "XVF3800 not detected. Check:"
  warn "  • USB cable is plugged in"
  warn "  • Run: lsusb | grep 2886"
  warn "  • Try a different USB port (USB 3 hub, not 2)"
fi

# ── List ALSA playback devices ────────────────────────────────
echo ""
info "ALSA playback devices (speakers):"
if aplay -l 2>/dev/null; then
  echo ""
else
  warn "aplay not found — install alsa-utils: sudo apt install -y alsa-utils"
fi

# ── PipeWire / PulseAudio status ──────────────────────────────
echo ""
info "PipeWire / PulseAudio status:"
if command -v pw-cli &>/dev/null; then
  echo "  PipeWire version: $(pw-cli --version 2>/dev/null || echo unknown)"
  if pactl info 2>/dev/null | grep -q "PipeWire"; then
    ok "PipeWire is running with PulseAudio compatibility"
  else
    warn "PipeWire PulseAudio compat layer not active"
    warn "  Try: systemctl --user enable --now pipewire pipewire-pulse wireplumber"
  fi
elif command -v pulseaudio &>/dev/null; then
  echo "  PulseAudio: $(pulseaudio --version)"
  ok "PulseAudio is available"
else
  warn "Neither PipeWire nor PulseAudio found"
fi

# ── Show PulseAudio/PipeWire sources and sinks ────────────────
echo ""
if command -v pactl &>/dev/null; then
  info "Audio sources (microphones):"
  pactl list short sources 2>/dev/null || true
  echo ""
  info "Audio sinks (speakers/output):"
  pactl list short sinks 2>/dev/null || true
  echo ""

  info "Default source (mic):"
  pactl get-default-source 2>/dev/null || echo "  (unknown)"
  info "Default sink (speaker):"
  pactl get-default-sink 2>/dev/null || echo "  (unknown)"
fi

# ── Set XVF3800 as default source ─────────────────────────────
echo ""
info "Looking for XVF3800 in PulseAudio/PipeWire sources …"
XVF_SOURCE=$(pactl list short sources 2>/dev/null | grep -i "xvf\|respeaker\|2886" | awk '{print $2}' | head -1 || true)
if [ -n "$XVF_SOURCE" ]; then
  info "Found XVF3800 source: ${XVF_SOURCE}"
  pactl set-default-source "$XVF_SOURCE" 2>/dev/null && ok "Set ${XVF_SOURCE} as default source"
else
  warn "XVF3800 not found in PulseAudio source list."
  warn "Try these steps:"
  warn "  1. Unplug and re-plug the XVF3800"
  warn "  2. Run: pactl list short sources"
  warn "  3. Find the source name containing 'XVF' or 'respeaker'"
  warn "  4. Run: pactl set-default-source <source-name>"
  warn "  5. Or set MIC_NAME in your .env to the substring that matches"
fi

# ── ALSA permissions check ────────────────────────────────────
echo ""
info "Checking ALSA permissions …"
if groups | grep -qw "audio"; then
  ok "Current user is in the 'audio' group"
else
  warn "Current user is NOT in the 'audio' group"
  warn "  Fix: sudo usermod -aG audio \$USER && sudo reboot"
fi

# ── Sample rate info ──────────────────────────────────────────
echo ""
info "XVF3800 sample rate information:"
echo "  The XVF3800 captures at 48 kHz natively."
echo "  Jansky resamples (decimates) to 16 kHz for Whisper/openWakeWord."
echo "  Ensure mic_sample_rate=48000 in config/config.json (default)."
echo ""

# ── Test recording ────────────────────────────────────────────
echo ""
info "Mic test recording (${RECORD_DURATION} seconds) …"
echo "  Speak into the XVF3800 now …"

if arecord \
    -D default \
    -f S16_LE \
    -r 48000 \
    -c 1 \
    -d "$RECORD_DURATION" \
    "$TEST_WAV" 2>/dev/null; then
  ok "Recorded to ${TEST_WAV}"
  echo ""
  info "Playing back recording …"
  aplay "$TEST_WAV" 2>/dev/null && ok "Playback complete" || \
    warn "aplay playback failed — try: mpg123 ${TEST_WAV} or paplay ${TEST_WAV}"
else
  warn "Recording failed. Try:"
  warn "  arecord -l                       # list devices"
  warn "  arecord -D hw:CARD=XVF3800 ...  # use explicit card name"
  warn "  Check: sudo dmesg | grep -i xvf"
fi

# ── Cleanup ───────────────────────────────────────────────────
rm -f "$TEST_WAV"

echo ""
echo "════════════════════════════════════════════════════"
echo "  Audio configuration complete."
echo "  See docs/pi5_setup.md for more troubleshooting."
echo "════════════════════════════════════════════════════"
echo ""
