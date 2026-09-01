#!/usr/bin/python3
"""Linux Mint Hub — Enhancement Hub for Linux Mint.

A native GTK3 desktop app for browsing, installing, and managing
Linux Mint enhancements (themes, icons, cursors, wallpapers, applets,
and more).
"""

import logging
import os
import sys

import gi
gi.require_version("Gtk", "3.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

if os.getuid() == 0:
    print("Linux Mint Hub should not be run as root.")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from application import MintHubApp

app = MintHubApp()
app.run(sys.argv)
