#!/bin/bash
set -euo pipefail

echo "▸ Stopping and disabling service..."
systemctl --user disable --now ctrl-hold-voice.service 2>/dev/null || true

echo "▸ Removing service file..."
rm -f "${HOME}/.config/systemd/user/ctrl-hold-voice.service"
systemctl --user daemon-reload

echo "▸ Removing daemon..."
rm -f "${HOME}/.local/bin/voice_daemon.py"

echo "▸ Removing GNOME extension..."
rm -rf "${HOME}/.local/share/gnome-shell/extensions/voice-indicator@ctrl-hold-voice"

echo "✓ Uninstalled. Restart GNOME Shell (Alt+F2 → r) to remove the indicator."
