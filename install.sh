#!/bin/bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# install.sh — sets up the Ctrl-Hold-Voice daemon + GNOME extension
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_SRC="${SCRIPT_DIR}/voice_daemon.py"
SERVICE_SRC="${SCRIPT_DIR}/systemd/ctrl-hold-voice.service"
EXTENSION_SRC="${SCRIPT_DIR}/gnome-extension"

INSTALL_BIN="${HOME}/.local/bin"
INSTALL_DAEMON="${INSTALL_BIN}/voice_daemon.py"
SERVICE_DST="${HOME}/.config/systemd/user/ctrl-hold-voice.service"
EXTENSION_DST="${HOME}/.local/share/gnome-shell/extensions/voice-indicator@ctrl-hold-voice"

# ── Colors ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▸${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
die()   { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Preflight ────────────────────────────────────────────────────
info "Checking dependencies..."

command -v pw-record >/dev/null 2>&1 || die "pw-record not found. Install: sudo apt install pipewire-audio-client-libraries"
command -v pactl >/dev/null 2>&1     || die "pactl not found. Install: sudo apt install pulseaudio-utils"
pkg-config --exists gtk+-3.0 2>/dev/null || die "GTK3 development files not found. Install: sudo apt install gir1.2-gtk-3.0"

# Find a usable Python with whisper + xlib
PYTHON=""
for candidate in "${VOICE_PYTHON:-}" python3 "${HOME}/ai-server-env/bin/python3"; do
    if [[ -n "$candidate" ]] && "$candidate" -c "import whisper, Xlib" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [[ -z "$PYTHON" ]]; then
    warn "No Python found with whisper + python3-xlib installed."
    info  "Create a venv and run: pip install -r requirements.txt"
    info  "Then re-run with: VOICE_PYTHON=/path/to/venv/bin/python3 ./install.sh"
    read -rp "  Use system python3 anyway? [y/N] " yn
    [[ "$yn" =~ ^[Yy]$ ]] || die "Aborted. Install dependencies first."
    PYTHON="python3"
fi
ok "Python: ${PYTHON}"

if ! "$PYTHON" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    warn "CUDA not available in this Python. Whisper will fall back to CPU (much slower)."
    warn "For GPU acceleration, install torch with CUDA support."
fi

# ── Detect microphone ────────────────────────────────────────────
info "Detecting microphone..."

MIC_TARGET="${VOICE_MIC_TARGET:-}"
if [[ -z "$MIC_TARGET" ]]; then
    info "Available audio sources:"
    pactl list short sources | grep -v '\.monitor$' | cat -n
    echo ""
    read -rp "  Enter the source name or number for your microphone (or set VOICE_MIC_TARGET env): " selection
    if [[ "$selection" =~ ^[0-9]+$ ]]; then
        MIC_TARGET=$(pactl list short sources | grep -v '\.monitor$' | sed -n "${selection}p" | awk '{print $2}')
    else
        MIC_TARGET="$selection"
    fi
    [[ -n "$MIC_TARGET" ]] || die "No microphone selected."
fi
ok "Microphone: ${MIC_TARGET}"

# ── Install daemon ───────────────────────────────────────────────
info "Installing daemon to ${INSTALL_DAEMON}..."
mkdir -p "$INSTALL_BIN"
cp "$DAEMON_SRC" "$INSTALL_DAEMON"
chmod +x "$INSTALL_DAEMON"
ok "Daemon installed."

# ── Generate systemd service ─────────────────────────────────────
info "Generating systemd service..."
mkdir -p "$(dirname "$SERVICE_DST")"

UID_NUM="$(id -u)"

# Escape paths for systemd
ESC_PYTHON="${PYTHON// /\\s20}"
ESC_DAEMON="${INSTALL_DAEMON// /\\s20}"

sed \
    -e "s|__PYTHON__|${ESC_PYTHON}|g" \
    -e "s|__DAEMON__|${ESC_DAEMON}|g" \
    -e "s|__UID__|${UID_NUM}|g" \
    -e "s|__MIC_TARGET__|${MIC_TARGET}|g" \
    "$SERVICE_SRC" > "$SERVICE_DST"

ok "Service generated: ${SERVICE_DST}"

# ── Enable lingering ──────────────────────────────────────────────
info "Enabling lingering so the service starts at boot..."
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    sudo loginctl enable-linger "$USER" 2>/dev/null || warn "Could not enable linger. Run manually: sudo loginctl enable-linger \$USER"
fi
ok "Linger enabled."

# ── Install GNOME extension ──────────────────────────────────────
info "Installing GNOME Shell extension..."
mkdir -p "$(dirname "$EXTENSION_DST")"
rm -rf "$EXTENSION_DST"
cp -r "$EXTENSION_SRC" "$EXTENSION_DST"
ok "Extension installed to ${EXTENSION_DST}"
warn "To enable: restart GNOME Shell (Alt+F2 → r), then enable in Extensions app or:"
warn "  gnome-extensions enable voice-indicator@ctrl-hold-voice"

# ── Reload & enable service ───────────────────────────────────────
info "Reloading systemd and enabling service..."
systemctl --user daemon-reload
systemctl --user enable --now ctrl-hold-voice.service
sleep 3

if systemctl --user is-active --quiet ctrl-hold-voice.service; then
    ok "Service is running!"
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Ctrl-Hold-Voice is installed!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════${NC}"
    echo ""
    echo "  Hold Ctrl for 0.5s to start recording."
    echo "  Release to transcribe and paste."
    echo ""
    echo "  View logs:    journalctl --user -u ctrl-hold-voice -f"
    echo "  Stop:         systemctl --user stop ctrl-hold-voice"
    echo "  Uninstall:    ${SCRIPT_DIR}/uninstall.sh"
    echo ""
else
    warn "Service did not start cleanly. Check logs:"
    warn "  journalctl --user -u ctrl-hold-voice -n 30"
fi
