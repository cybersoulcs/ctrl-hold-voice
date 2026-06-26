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

# Restore GNOME Terminal paste shortcut if we backed it up
BACKUP_DIR="${HOME}/.config/voice-input"
if [[ -f "${BACKUP_DIR}/gnome-terminal-paste-schema" && -f "${BACKUP_DIR}/gnome-terminal-paste-original" ]]; then
    echo "▸ Restoring GNOME Terminal paste shortcut..."
    SCHEMA=$(cat "${BACKUP_DIR}/gnome-terminal-paste-schema")
    ORIGINAL=$(cat "${BACKUP_DIR}/gnome-terminal-paste-original")
    if command -v gsettings >/dev/null 2>&1; then
        gsettings set "${SCHEMA}" paste "${ORIGINAL}" && \
            echo "  ✓ Restored paste to ${ORIGINAL}" || \
            echo "  ! Could not restore automatically. Run manually:"
        echo "    gsettings set ${SCHEMA} paste ${ORIGINAL}"
    fi
    rm -rf "${BACKUP_DIR}"
fi

echo "✓ Uninstalled. Restart GNOME Shell (Alt+F2 → r) to remove the indicator."
