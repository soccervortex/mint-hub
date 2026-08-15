"""Async thumbnail and image loading with caching."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib

from constants import THUMBNAIL_CACHE_DIR

THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_MAX_CACHE = 500
_pixbuf_cache: dict[str, GdkPixbuf.Pixbuf] = {}
_cache_order: list[str] = []
_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="mh-img")


def load_thumbnail_async(source: str, size: int, callback, fallback_icon: str = "image-missing"):
    if not source:
        GLib.idle_add(callback, _icon_pixbuf(fallback_icon, size))
        return
    cached = _pixbuf_cache.get(f"{source}:{size}")
    if cached:
        GLib.idle_add(callback, cached)
        return
    _pool.submit(_load_worker, source, size, callback, fallback_icon)


def _load_worker(source: str, size: int, callback, fallback_icon: str):
    try:
        if source.startswith(("http://", "https://")):
            import requests
            cache_key = source.split("/")[-1]
            cache_path = THUMBNAIL_CACHE_DIR / cache_key
            if not cache_path.exists():
                resp = requests.get(source, timeout=15)
                resp.raise_for_status()
                cache_path.write_bytes(resp.content)
            source = str(cache_path)

        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(source, size, size, True)
        key = f"{source}:{size}"
        if len(_pixbuf_cache) >= _MAX_CACHE and _cache_order:
            oldest = _cache_order.pop(0)
            _pixbuf_cache.pop(oldest, None)
        _pixbuf_cache[key] = pb
        _cache_order.append(key)
        GLib.idle_add(callback, pb)
    except Exception:
        GLib.idle_add(callback, _icon_pixbuf(fallback_icon, size))


def _icon_pixbuf(icon_name: str, size: int) -> GdkPixbuf.Pixbuf:
    key = f"icon:{icon_name}:{size}"
    if key in _pixbuf_cache:
        return _pixbuf_cache[key]
    theme = Gtk.IconTheme.get_default()
    try:
        pb = theme.load_icon(icon_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
        if pb:
            _pixbuf_cache[key] = pb
            return pb
    except Exception:
        pass
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, size, size)
    pb.fill(0x33333355)
    _pixbuf_cache[key] = pb
    return pb


def get_category_icon(icon_name: str, size: int = 24) -> GdkPixbuf.Pixbuf:
    return _icon_pixbuf(icon_name, size)


def clear_cache():
    _pixbuf_cache.clear()
