# Ctrl-Hold-Voice

Press-to-talk voice input for Linux. **Hold Ctrl for half a second, speak, release** — your words are transcribed on GPU with [OpenAI Whisper](https://github.com/openai/whisper), optionally polished by an LLM, and pasted directly into whatever window has focus.

No hotkey to toggle on/off, no UI to fumble with, no always-on microphone. Just hold Ctrl when you want to dictate.

## How it works

```
Hold Ctrl ──▶ Record (PipeWire) ──▶ Transcribe (Whisper GPU) ──▶ Polish (LLM, optional) ──▶ Paste
```

The daemon stays resident so the Whisper model loads **once** at startup (~3s) and stays warm in GPU memory. Every subsequent dictation skips model loading entirely.

## Requirements

- **Linux** with X11 (Wayland is not supported due to X11-based key detection)
- **NVIDIA GPU** with CUDA (CPU fallback works but is ~10x slower)
- **PipeWire** (`pw-record`) — standard on modern desktop Linux
- **Python 3.10+**
- **GNOME Shell 45/46/47** (only needed for the optional status indicator)

### System packages (Ubuntu/Debian)

```bash
sudo apt install pipewire-audio-client-libraries pulseaudio-utils \
    gir1.2-gtk-3.0 python3-gi
```

### Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> For GPU acceleration, follow the [PyTorch CUDA install guide](https://pytorch.org/get-started/locally/) for your platform.

## Quick install

```bash
git clone https://github.com/YOUR_USERNAME/ctrl-hold-voice.git
cd ctrl-hold-voice
./install.sh
```

`install.sh` is interactive: it detects your microphone, asks you to confirm, generates the systemd service, enables boot-time startup, installs the GNOME indicator, and starts everything.

## Usage

1. **Hold Ctrl** for ~0.5 seconds. The top-bar indicator turns red (● REC).
2. **Speak.** Your microphone records while Ctrl is held.
3. **Release Ctrl.** The indicator cycles through ↻ STT → ⚙ AI → ✓, then the text appears at your cursor.

### GNOME indicator states

| Icon | Text | Meaning |
|------|------|---------|
| 🔴 | ● REC | Recording in progress |
| 🟡 | ↻ STT | Whisper transcribing |
| 🔵 | ⚙ AI | LLM correcting |
| 🟢 | ✓ | Done |
| 🔴 | ⚠ | Error (no speech / failure) |

## Configuration

All settings are environment variables, set in the generated systemd service file at `~/.config/systemd/user/ctrl-hold-voice.service`. Edit and `systemctl --user restart ctrl-hold-voice` to apply.

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_MIC_TARGET` | *(required)* | PipeWire source name. Find with `pactl list short sources` |
| `VOICE_HOLD_SECONDS` | `0.5` | How long to hold Ctrl before recording starts |
| `VOICE_WHISPER_MODEL` | `medium` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `VOICE_WHISPER_DEVICE` | `cuda` | `cuda` or `cpu` |
| `VOICE_BEAM_SIZE` | `1` | Decoding beam width. Lower = faster, slightly less accurate |
| `VOICE_WHISPER_LANGUAGE` | `zh` | Language code for transcription |
| `VOICE_LLM_ENABLED` | `1` | `1` to run LLM post-processing, `0` to disable |
| `VOICE_LLM_URL` | `http://127.0.0.1:8000/...` | OpenAI-compatible API endpoint |
| `VOICE_LLM_MODEL` | `default` | Model name for the LLM endpoint |
| `VOICE_PASTE_MODS` | `ctrl` | Modifier keys for paste (`ctrl`, `shift`, `ctrl+shift`). Ctrl+V works in virtually all apps |

## Performance

Benchmarked on NVIDIA GB10 (aarch64, Jetson class), 3-second utterance:

| Stage | Time |
-------|------|
| Whisper `medium` (beam=1, CUDA) | ~0.15s |
| Whisper `medium` (beam=5, CUDA) | ~0.35s |
| LLM correction (short sentence) | ~0.18s |
| Clipboard + paste | ~0.30s |
| **Total (release → text appears)** | **~0.6s** |

## File structure

```
ctrl-hold-voice/
├── voice_daemon.py          # Core daemon: key detection, recording, transcription, paste
├── clipboard_set.py         # Clipboard helper (GTK3, runs as subprocess)
├── install.sh               # Interactive installer
├── uninstall.sh             # Clean uninstaller
├── requirements.txt         # Python dependencies
├── systemd/
│   └── ctrl-hold-voice.service   # Service template (placeholders filled by install.sh)
└── gnome-extension/
    ├── metadata.json        # GNOME Shell extension metadata
    └── extension.js         # Top-bar status indicator
```

## How key detection works

The daemon polls the X server's keymap via `XQueryKeymap` every 100ms. When Ctrl is detected as held for `HOLD_SECONDS`, recording begins. When Ctrl is released, the session ends. This means no kernel-level input hooks, no `/dev/input` permissions, and no interference with normal Ctrl-based shortcuts (Ctrl+C, Ctrl+S, etc.) — the hold duration distinguishes dictation from shortcuts.

## Troubleshooting

**Ctrl doesn't respond.** Check the daemon is connected to the right display. The service hardcodes `DISPLAY=:1` by default; if your session uses a different display, update it in the service file. Verify with:
```bash
journalctl --user -u ctrl-hold-voice -f
```
You should see `X display :1 connected.` on startup. If you see repeated `Connection reset by peer`, the daemon is holding a stale X connection — restart it:
```bash
systemctl --user restart ctrl-hold-voice
```

**No audio recorded.** Verify your microphone target:
```bash
pactl list short sources
```
Ensure the name matches `VOICE_MIC_TARGET` in the service file. Test recording manually:
```bash
pw-record --target "YOUR_SOURCE" --rate 16000 --channels 1 --format s16 /tmp/test.wav
```

**LLM correction is slow.** Set `VOICE_LLM_ENABLED=0` to skip it entirely, or point `VOICE_LLM_URL` to a faster/smaller model. The daemon falls back gracefully — if the LLM is unreachable, it pastes the raw Whisper output.

## Uninstall

```bash
./uninstall.sh
```
Removes the daemon, service, and extension. Restart GNOME Shell to clear the indicator.

## License

[MIT](LICENSE)
