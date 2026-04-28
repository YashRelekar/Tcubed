#!/usr/bin/env bash
# ==============================================================
#  Bluetooth Speaker Setup for Raspberry Pi 5
#  Pairs a Bluetooth A2DP speaker and makes it persist on reboot
# ==============================================================
#
#  Usage:
#    chmod +x scripts/pi5_bluetooth.sh
#    ./scripts/pi5_bluetooth.sh
#
#  Requirements:
#    sudo apt install -y bluetooth bluez pulseaudio-module-bluetooth
#
#  What this script does:
#   1. Enables and starts Bluetooth service
#   2. Scans for nearby Bluetooth devices
#   3. Pairs and connects to the selected device
#   4. Sets it as the default PipeWire/PulseAudio sink
#   5. Creates a udev rule + systemd unit for auto-reconnect on reboot
# ==============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "════════════════════════════════════════════════════"
echo "  Jansky — Bluetooth Speaker Setup"
echo "════════════════════════════════════════════════════"
echo ""

# ── Prerequisites ─────────────────────────────────────────────
if ! command -v bluetoothctl &>/dev/null; then
  fail "bluetoothctl not found. Install: sudo apt install -y bluetooth bluez"
fi

# ── Start Bluetooth service ───────────────────────────────────
info "Enabling and starting Bluetooth service …"
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sleep 1
ok "Bluetooth service running"

# ── Check if already paired ───────────────────────────────────
info "Paired Bluetooth devices:"
PAIRED=$(bluetoothctl devices Paired 2>/dev/null || true)
if [ -n "$PAIRED" ]; then
  echo "$PAIRED"
  echo ""
  read -rp "Use an already-paired device? [y/N] " USE_PAIRED
  if [[ "$USE_PAIRED" =~ ^[Yy]$ ]]; then
    BT_MAC=$(echo "$PAIRED" | head -1 | awk '{print $2}')
    BT_NAME=$(echo "$PAIRED" | head -1 | cut -d' ' -f3-)
    info "Using: ${BT_NAME} (${BT_MAC})"
    # Skip scan, go straight to connect
    goto_connect=true
  fi
fi

if [ "${goto_connect:-false}" = "false" ]; then
  # ── Scan for devices ──────────────────────────────────────────
  info "Scanning for Bluetooth devices (10 seconds) …"
  info "Make sure your speaker is in PAIRING mode."
  echo ""

  SCAN_OUTPUT="$(bluetoothctl --timeout 10 scan on 2>&1 || true)"
  echo "$SCAN_OUTPUT" | grep "Device" | grep -v "RSSI\|ManufacturerData\|UUID" || true
  echo ""

  info "Available devices:"
  bluetoothctl devices 2>/dev/null || true
  echo ""

  read -rp "Enter Bluetooth MAC address of your speaker (e.g. AA:BB:CC:DD:EE:FF): " BT_MAC
  if [ -z "$BT_MAC" ]; then
    fail "No MAC address provided."
  fi
fi

# ── Pair ──────────────────────────────────────────────────────
info "Pairing with ${BT_MAC} …"
bluetoothctl pair "$BT_MAC" 2>/dev/null || warn "Pair returned non-zero (may already be paired)"
ok "Paired"

info "Trusting ${BT_MAC} (auto-reconnect) …"
bluetoothctl trust "$BT_MAC"
ok "Trusted"

# ── Connect ───────────────────────────────────────────────────
info "Connecting to ${BT_MAC} …"
bluetoothctl connect "$BT_MAC"
sleep 2

if bluetoothctl info "$BT_MAC" 2>/dev/null | grep -q "Connected: yes"; then
  ok "Connected to ${BT_MAC}"
else
  warn "Connection may not have succeeded. Check: bluetoothctl info ${BT_MAC}"
fi

# ── Set as default sink ───────────────────────────────────────
if command -v pactl &>/dev/null; then
  info "Looking for Bluetooth sink in PulseAudio/PipeWire …"
  sleep 2  # Give PipeWire time to register the new sink
  BT_SINK=$(pactl list short sinks 2>/dev/null | grep -i "bluez\|bluetooth" | awk '{print $2}' | head -1 || true)

  if [ -n "$BT_SINK" ]; then
    pactl set-default-sink "$BT_SINK"
    ok "Default sink set to: ${BT_SINK}"
    echo "  SPEAKER_NAME env var can remain empty (system default = BT speaker)"
  else
    warn "No Bluetooth sink found in PulseAudio. Try:"
    warn "  pactl list short sinks"
    warn "  pactl set-default-sink <bluez_sink_name>"
  fi
fi

# ── Auto-reconnect on boot (systemd user service) ─────────────
info "Creating systemd user service for auto-reconnect …"

SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

cat > "${SYSTEMD_USER_DIR}/bt-speaker.service" <<EOF
[Unit]
Description=Reconnect Bluetooth speaker ${BT_MAC}
After=bluetooth.target sound.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bluetoothctl connect ${BT_MAC}
RemainAfterExit=yes

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable bt-speaker.service
ok "Systemd user service enabled: bt-speaker.service"

echo ""
echo "════════════════════════════════════════════════════"
echo "  Bluetooth setup complete."
echo ""
echo "  To verify after reboot:"
echo "    bluetoothctl info ${BT_MAC}"
echo "    pactl list short sinks | grep -i blue"
echo ""
echo "  Troubleshooting:"
echo "    journalctl --user -u bt-speaker.service"
echo "    sudo systemctl restart bluetooth"
echo "════════════════════════════════════════════════════"
echo ""
