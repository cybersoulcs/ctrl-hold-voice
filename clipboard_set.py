#!/usr/bin/env python3
"""Standalone clipboard helper using GTK3.

Reads text from stdin and copies it to the system clipboard.
Useful as a fallback when the in-process clipboard (in voice_daemon.py)
is unavailable, or from other scripts.
"""
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

text = sys.stdin.read()
clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
clip.set_text(text, -1)

GLib.timeout_add(100, Gtk.main_quit)
Gtk.main()
