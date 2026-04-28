#!/usr/bin/env bash
# ==============================================================
#  Jansky — One-Command Installer (shortcut)
#  Delegates to scripts/pi5_setup.sh
# ==============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/pi5_setup.sh" "$@"
