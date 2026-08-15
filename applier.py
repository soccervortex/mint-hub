"""Apply/revert enhancements via Gio.Settings (gsettings)."""

import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio

from constants import GSETTINGS_MAP
from enhancement import Enhancement


class EnhancementApplier:
    def __init__(self):
        self._previous = {}

    def get_current(self, category: str) -> str:
        entry = GSETTINGS_MAP.get(category)
        if not entry:
            return ""
        schema_id, key = entry
        try:
            settings = Gio.Settings.new(schema_id)
            return settings.get_string(key)
        except Exception:
            return ""

    def apply(self, enh: Enhancement) -> bool:
        category = enh.category
        entry = GSETTINGS_MAP.get(category)
        if entry:
            return self._apply_gsetting(category, enh)
        if category == "font":
            return self._apply_font(enh)
        if category in ("applet", "desklet", "extension"):
            return self._reload_cinnamon()
        if enh.apply_command:
            return self._run_command(enh.apply_command)
        return False

    def revert(self, category: str, previous_value: str) -> bool:
        entry = GSETTINGS_MAP.get(category)
        if not entry:
            return False
        schema_id, key = entry
        try:
            settings = Gio.Settings.new(schema_id)
            settings.set_string(key, previous_value)
            return True
        except Exception:
            return False

    def _apply_gsetting(self, category: str, enh: Enhancement) -> bool:
        entry = GSETTINGS_MAP.get(category)
        if not entry:
            return False
        schema_id, key = entry
        self._previous[category] = self.get_current(category)
        try:
            settings = Gio.Settings.new(schema_id)
            if category == "wallpaper":
                value = f"file://{enh.install_path}"
            else:
                value = enh.name
            settings.set_string(key, value)
            return True
        except Exception:
            return False

    def _apply_font(self, enh: Enhancement) -> bool:
        try:
            subprocess.run(["fc-cache", "-f", str(enh.install_path)],
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    def _reload_cinnamon(self) -> bool:
        try:
            subprocess.run(
                ["dbus-send", "--session", "--dest=org.Cinnamon",
                 "--type=method_call", "/org/Cinnamon",
                 "org.Cinnamon.ReloadXlets"],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    def _run_command(self, command: str) -> bool:
        try:
            parts = command.split()
            subprocess.run(parts, capture_output=True, timeout=60)
            return True
        except Exception:
            return False

    def get_previous(self, category: str) -> str:
        return self._previous.get(category, "")
