#!/usr/bin/env python3
"""Voice input daemon with persistent CUDA model.

Hold Ctrl for HOLD_SECONDS to start recording. Release to stop.
The recording is transcribed with OpenAI Whisper on GPU, optionally
corrected by an LLM, then pasted into the focused window.

All settings are configurable via environment variables — see README.md.
"""
import os, sys, time, subprocess, numpy as np
from Xlib import X, XK, display
from Xlib.ext import xtest

# ── Configuration (override via environment variables) ──────────────────
MIC_TARGET = os.environ.get("VOICE_MIC_TARGET", "")
WAV_FILE = os.environ.get("VOICE_WAV_FILE", "/tmp/voice_stream.wav")
LLM_URL = os.environ.get("VOICE_LLM_URL", "http://127.0.0.1:8000/v1/chat/completions")
LLM_MODEL = os.environ.get("VOICE_LLM_MODEL", "default")
LLM_ENABLED = os.environ.get("VOICE_LLM_ENABLED", "1") == "1"
DISPLAY_STR = os.environ.get("DISPLAY", ":1")
HOLD_SECONDS = float(os.environ.get("VOICE_HOLD_SECONDS", "0.5"))
WHISPER_MODEL = os.environ.get("VOICE_WHISPER_MODEL", "medium")
WHISPER_DEVICE = os.environ.get("VOICE_WHISPER_DEVICE", "cuda")
WHISPER_BEAM_SIZE = int(os.environ.get("VOICE_BEAM_SIZE", "1"))
WHISPER_LANGUAGE = os.environ.get("VOICE_WHISPER_LANGUAGE", "zh")
STATUS_FILE = os.environ.get("VOICE_STATUS_FILE", "/tmp/voice_status")
PASTE_MODS = os.environ.get("VOICE_PASTE_MODS", "ctrl+shift")  # ctrl, shift, or ctrl+shift

_dpy = None
_model = None






def get_dpy():
    global _dpy
    if _dpy is not None:
        try:
            _dpy.flush()
        except Exception:
            _dpy = None
    if _dpy is None:
        while True:
            try:
                _dpy = display.Display(DISPLAY_STR)
                _dpy.flush()
                print(f"X display {DISPLAY_STR} connected.", flush=True)
                break
            except Exception as e:
                print(f"Waiting for X display {DISPLAY_STR}: {e}", flush=True)
                time.sleep(2)
    return _dpy


def load_model():
    global _model
    if _model is None:
        import whisper
        print(f"Loading whisper {WHISPER_MODEL} on {WHISPER_DEVICE}...", flush=True)
        _model = whisper.load_model(WHISPER_MODEL, device=WHISPER_DEVICE)
        print("Model ready.", flush=True)
    return _model


def notify(msg):
    """Write status to file for the GNOME Shell extension to read."""
    status_map = {
        "Recording...": "recording",
        "Transcribing...": "transcribing",
        "Correcting...": "correcting",
        "Done": "done",
    }
    status = "idle"
    for key, val in status_map.items():
        if key in msg:
            status = val
            break
    if "No speech" in msg or "error" in msg.lower():
        status = "error"
    try:
        with open(STATUS_FILE, "w") as f:
            f.write(status)
    except Exception:
        pass
    if status in ("done", "error"):
        import threading
        def reset():
            time.sleep(2)
            try:
                with open(STATUS_FILE, "w") as f:
                    f.write("idle")
            except Exception:
                pass
        t = threading.Thread(target=reset, daemon=True)
        t.start()


def paste_text(text):
    if not text:
        return
    # Use the standalone clipboard helper as a subprocess. GTK clipboard
    # operations require a running GLib main loop, which this polling
    # daemon does not have, so an in-process approach would hang.
    clipboard_helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipboard_set.py")
    subprocess.run(["python3", clipboard_helper], input=text, text=True)
    time.sleep(0.1)
    dpy = get_dpy()
    mods = PASTE_MODS.split("+")
    mod_keys = {
        "ctrl": XK.XK_Control_L,
        "shift": XK.XK_Shift_L,
        "alt": XK.XK_Alt_L,
        "super": XK.XK_Super_L,
    }
    held = []
    for mod in mods:
        kc = dpy.keysym_to_keycode(mod_keys.get(mod.strip(), XK.XK_Control_L))
        held.append(kc)
        xtest.fake_input(dpy, X.KeyPress, kc)
    v = dpy.keysym_to_keycode(XK.string_to_keysym("v"))
    xtest.fake_input(dpy, X.KeyPress, v)
    xtest.fake_input(dpy, X.KeyRelease, v)
    for kc in reversed(held):
        xtest.fake_input(dpy, X.KeyRelease, kc)
    dpy.flush()
    time.sleep(0.03)


def is_ctrl_down():
    dpy = get_dpy()
    km = dpy.query_keymap()
    ctrl_l = dpy.keysym_to_keycode(XK.XK_Control_L)
    ctrl_r = dpy.keysym_to_keycode(XK.XK_Control_R)
    return ((ctrl_l < 256 and km[ctrl_l // 8] & (1 << (ctrl_l % 8))) or
            (ctrl_r < 256 and km[ctrl_r // 8] & (1 << (ctrl_r % 8))))


def read_wav_samples(path):
    try:
        size = os.path.getsize(path)
        if size <= 44:
            return np.array([], dtype=np.float32)
        with open(path, "rb") as f:
            f.seek(44)
            raw = f.read()
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return np.array([], dtype=np.float32)


def transcribe(path):
    model = load_model()
    samples = read_wav_samples(path)
    if len(samples) < 1600:
        return ""
    result = model.transcribe(samples, language=WHISPER_LANGUAGE,
                              beam_size=WHISPER_BEAM_SIZE, verbose=False)
    return result["text"].strip()


def llm_cleanup(text):
    if not LLM_ENABLED:
        return text
    import requests
    try:
        resp = requests.post(LLM_URL, json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are a speech-to-text proofreader. Fix typos, punctuation, "
                    "and word order in the following transcription while preserving "
                    "the original meaning. Output only the corrected text."
                )},
                {"role": "user", "content": text},
            ],
            "max_tokens": 2000, "temperature": 0.3, "stream": False,
        }, timeout=120)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM error (falling back to raw transcription): {e}", flush=True)
        return text


def voice_session():
    """Record while Ctrl held, transcribe + correct on release."""
    notify("Recording...")
    if os.path.exists(WAV_FILE):
        os.remove(WAV_FILE)

    proc = subprocess.Popen(
        ["pw-record", "--target", MIC_TARGET, "--rate", "16000",
         "--channels", "1", "--format", "s16", WAV_FILE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    while is_ctrl_down():
        time.sleep(0.1)

    proc.terminate()
    proc.wait()
    notify("Transcribing...")

    rough_text = transcribe(WAV_FILE)
    if not rough_text:
        notify("No speech detected")
        if os.path.exists(WAV_FILE):
            os.remove(WAV_FILE)
        return

    notify("Correcting...")
    corrected = llm_cleanup(rough_text)
    paste_text(corrected)
    notify("Done")

    if os.path.exists(WAV_FILE):
        os.remove(WAV_FILE)


def main():
    if not MIC_TARGET:
        print("ERROR: VOICE_MIC_TARGET is not set. Run 'pactl list short sources' "
              "to find your microphone, then set it in the service file.", flush=True)
        sys.exit(1)

    get_dpy()
    load_model()

    print(f"Voice daemon ready. Hold Ctrl {HOLD_SECONDS:.1f}s to start.", flush=True)
    print(f"  Mic:     {MIC_TARGET}", flush=True)
    print(f"  Whisper: {WHISPER_MODEL} on {WHISPER_DEVICE} (beam={WHISPER_BEAM_SIZE})", flush=True)
    print(f"  LLM:     {'enabled → ' + LLM_URL if LLM_ENABLED else 'disabled'}", flush=True)

    ctrl_since = None
    busy = False

    while True:
        try:
            held = is_ctrl_down()
            now = time.time()

            if not busy:
                if held:
                    if ctrl_since is None:
                        ctrl_since = now
                    elif now - ctrl_since >= HOLD_SECONDS:
                        print("Ctrl held -> voice session", flush=True)
                        busy = True
                        ctrl_since = None
                        voice_session()
                        busy = False
                else:
                    ctrl_since = None
            time.sleep(0.1)

        except KeyboardInterrupt:
            print("Shutting down...", flush=True)
            break
        except Exception as e:
            print(f"Error: {e}", flush=True)
            busy = False
            time.sleep(1)


if __name__ == "__main__":
    main()
