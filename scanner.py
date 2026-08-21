"""Scans the local filesystem for installed enhancements."""

import configparser
import json
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio

from constants import SCAN_PATHS, GSETTINGS_MAP, IMAGE_EXTENSIONS, FONT_EXTENSIONS
from enhancement import Enhancement
from imaging import make_font_preview


class LocalScanner:
    def scan_all(self) -> list:
        results = []
        results.extend(self._scan_themes("gtk-theme"))
        results.extend(self._scan_themes("cinnamon-theme"))
        results.extend(self._scan_icon_themes())
        results.extend(self._scan_cursor_themes())
        results.extend(self._scan_wallpapers())
        results.extend(self._scan_xlets("applet"))
        results.extend(self._scan_xlets("desklet"))
        results.extend(self._scan_xlets("extension"))
        results.extend(self._scan_fonts())
        return results

    def detect_applied(self) -> dict:
        applied = {}
        for category, (schema_id, key) in GSETTINGS_MAP.items():
            try:
                settings = Gio.Settings.new(schema_id)
                val = settings.get_string(key)
                if val:
                    applied[category] = val
            except Exception:
                pass
        return applied

    def _scan_themes(self, category: str) -> list:
        subdir = "gtk-3.0" if category == "gtk-theme" else "cinnamon"
        results = []
        seen = set()
        for base in SCAN_PATHS.get(category, []):
            if not base.exists():
                continue
            try:
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir() or entry.name.startswith("."):
                        continue
                    if entry.name in seen:
                        continue
                    if (entry / subdir).is_dir():
                        seen.add(entry.name)
                        writable = os.access(str(entry), os.W_OK)
                        summary = self._read_theme_comment(entry)
                        thumb = self._find_theme_thumbnail(entry)
                        results.append(Enhancement.from_local(
                            name=entry.name,
                            category=category,
                            path=str(entry),
                            summary=summary,
                            thumbnail_local=thumb,
                            writable=writable,
                        ))
            except PermissionError:
                continue
        return results

    def _scan_icon_themes(self) -> list:
        results = []
        seen = set()
        skip = {"hicolor", "default", "locolor"}
        for base in SCAN_PATHS.get("icon-theme", []):
            if not base.exists():
                continue
            try:
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir() or entry.name.startswith("."):
                        continue
                    if entry.name in seen or entry.name in skip:
                        continue
                    index = entry / "index.theme"
                    if not index.exists():
                        continue
                    if (entry / "cursors").is_dir():
                        continue
                    cp = configparser.ConfigParser()
                    try:
                        cp.read(str(index))
                        if not cp.has_section("Icon Theme"):
                            continue
                    except Exception:
                        continue
                    seen.add(entry.name)
                    comment = ""
                    try:
                        comment = cp.get("Icon Theme", "Comment", fallback="")
                    except Exception:
                        pass
                    thumb = self._find_icon_theme_preview(entry)
                    results.append(Enhancement.from_local(
                        name=entry.name,
                        category="icon-theme",
                        path=str(entry),
                        summary=comment,
                        thumbnail_local=thumb,
                        writable=os.access(str(entry), os.W_OK),
                    ))
            except PermissionError:
                continue
        return results

    def _scan_cursor_themes(self) -> list:
        results = []
        seen = set()
        for base in SCAN_PATHS.get("cursor-theme", []):
            if not base.exists():
                continue
            try:
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir() or entry.name.startswith("."):
                        continue
                    if entry.name in seen:
                        continue
                    if (entry / "cursors").is_dir():
                        seen.add(entry.name)
                        thumb = self._find_cursor_theme_preview(entry)
                        results.append(Enhancement.from_local(
                            name=entry.name,
                            category="cursor-theme",
                            path=str(entry),
                            thumbnail_local=thumb,
                            writable=os.access(str(entry), os.W_OK),
                        ))
            except PermissionError:
                continue
        return results

    def _scan_wallpapers(self) -> list:
        results = []
        seen = set()
        for base in SCAN_PATHS.get("wallpaper", []):
            if not base.exists():
                continue
            try:
                for f in sorted(base.rglob("*")):
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                        if f.name in seen:
                            continue
                        seen.add(f.name)
                        results.append(Enhancement.from_local(
                            name=f.stem,
                            category="wallpaper",
                            path=str(f),
                            thumbnail_local=str(f),
                            writable=os.access(str(f), os.W_OK),
                        ))
            except PermissionError:
                continue
        return results

    def _scan_xlets(self, xlet_type: str) -> list:
        results = []
        seen = set()
        for base in SCAN_PATHS.get(xlet_type, []):
            if not base.exists():
                continue
            try:
                for entry in sorted(base.iterdir()):
                    if not entry.is_dir():
                        continue
                    meta_file = entry / "metadata.json"
                    if not meta_file.exists():
                        continue
                    if entry.name in seen:
                        continue
                    seen.add(entry.name)
                    try:
                        meta = json.loads(meta_file.read_text())
                    except Exception:
                        continue
                    name = meta.get("name", entry.name)
                    summary = meta.get("description", "")
                    version = meta.get("version", "")
                    author = meta.get("author", "")
                    icon_path = ""
                    icon_file = entry / "icon.png"
                    if icon_file.exists():
                        icon_path = str(icon_file)
                    results.append(Enhancement.from_local(
                        name=name,
                        category=xlet_type,
                        path=str(entry),
                        slug=entry.name,
                        summary=summary,
                        version=str(version),
                        author=author,
                        thumbnail_local=icon_path,
                        writable=os.access(str(entry), os.W_OK),
                    ))
            except PermissionError:
                continue
        return results

    def _find_icon_theme_preview(self, theme_dir: Path) -> str:
        for name in ("thumbnail.png", "preview.png", "screenshot.png"):
            p = theme_dir / name
            if p.exists():
                return str(p)
        preferred_icons = ["folder", "system-file-manager", "utilities-terminal",
                           "firefox", "application-x-executable", "user-home"]
        for size_dir in ["48x48", "64x64", "32x32", "scalable"]:
            apps_dir = theme_dir / size_dir / "apps"
            places_dir = theme_dir / size_dir / "places"
            for search_dir in [places_dir, apps_dir]:
                if not search_dir.is_dir():
                    continue
                for icon_name in preferred_icons:
                    for ext in (".png", ".svg"):
                        candidate = search_dir / f"{icon_name}{ext}"
                        if candidate.exists():
                            return str(candidate)
                try:
                    for f in sorted(search_dir.iterdir()):
                        if f.suffix.lower() in (".png", ".svg") and f.stat().st_size > 100:
                            return str(f)
                except PermissionError:
                    pass
        return ""

    def _find_cursor_theme_preview(self, theme_dir: Path) -> str:
        for name in ("thumbnail.png", "preview.png", "screenshot.png"):
            p = theme_dir / name
            if p.exists():
                return str(p)
        return ""

    def _scan_fonts(self) -> list:
        results = []
        seen = set()
        for base in SCAN_PATHS.get("font", []):
            if not base.exists():
                continue
            try:
                for f in sorted(base.rglob("*")):
                    if f.is_file() and f.suffix.lower() in FONT_EXTENSIONS:
                        family = f.stem.replace("-", " ").replace("_", " ")
                        if family in seen:
                            continue
                        seen.add(family)
                        thumb = make_font_preview(str(f))
                        results.append(Enhancement.from_local(
                            name=family,
                            category="font",
                            path=str(f),
                            thumbnail_local=thumb,
                            writable=os.access(str(f), os.W_OK),
                        ))
            except PermissionError:
                continue
        return results

    def _read_theme_comment(self, theme_dir: Path) -> str:
        index = theme_dir / "index.theme"
        if not index.exists():
            return ""
        cp = configparser.ConfigParser()
        try:
            cp.read(str(index))
            return cp.get("Desktop Entry", "Comment", fallback="") or cp.get("X-GNOME-Metatheme", "Comment", fallback="")
        except Exception:
            return ""

    def _find_theme_thumbnail(self, theme_dir: Path) -> str:
        for name in ("thumbnail.png", "preview.png", "screenshot.png"):
            p = theme_dir / name
            if p.exists():
                return str(p)
        return ""
