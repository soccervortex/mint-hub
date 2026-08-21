"""Gtk.Application subclass — the core of Linux Mint Hub."""

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("XApp", "1.0")
from gi.repository import Gtk, Gio, GLib, XApp

from constants import (
    APP_ID, APP_NAME, APP_VERSION, CONFIG_DIR, CONFIG_FILE,
    CACHE_DIR, THUMBNAIL_CACHE_DIR,
)
from api_client import MintHubClient
from local_cache import LocalCache
from scanner import LocalScanner
from installer import EnhancementInstaller
from applier import EnhancementApplier
from enhancement import Enhancement
from threading_utils import _async
from spices_fetcher import fetch_all_spices
from seeder import load_catalog, seed_local
from window import MainWindow, PAGE_ONBOARDING, PAGE_LOADING, PAGE_HOME


log = logging.getLogger("minthub")


class MintHubApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.cache = LocalCache()
        self.scanner = LocalScanner()
        self.installer = EnhancementInstaller(self.cache)
        self.applier = EnhancementApplier()
        self.api = None
        self._omni_key = ""
        self.main_window = None

    def do_activate(self):
        self.main_window = MainWindow(self)
        window = self.main_window.build()

        key = self._load_key()
        if key:
            self._omni_key = key
            self.api = MintHubClient(key)
            self.main_window.navigate_to(PAGE_LOADING)
            self.start_init()
        else:
            self.main_window.navigate_to(PAGE_ONBOARDING)

    def try_connect(self, key: str) -> bool:
        try:
            client = MintHubClient(key)
            valid = client.validate_key()
            if valid:
                self._omni_key = key
                self.api = client
                self._save_key(key)
            return valid
        except Exception:
            return False

    @_async
    def start_init(self):
        GLib.idle_add(self.main_window.set_loading_text, "Scanning local enhancements...")
        local_items = self.scanner.scan_all()
        self.cache.upsert_many(local_items)
        GLib.idle_add(self.main_window.set_loading_text,
                      f"Found {len(local_items)} local enhancements. Loading catalog...")

        GLib.idle_add(self.main_window.set_loading_text, "Loading curated catalog...")
        try:
            seed_local()
        except Exception as e:
            log.warning(f"Seed catalog load failed: {e}")

        GLib.idle_add(self.main_window.set_loading_text, "Fetching catalogs...")

        def _fetch_spices():
            return fetch_all_spices()

        def _fetch_marketplace():
            if not self.api:
                return []
            result = self.api.list_enhancements(per_page=100)
            items = result.get("items", []) if isinstance(result, dict) else result
            return [Enhancement.from_api(item) for item in items]

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_spices = pool.submit(_fetch_spices)
            fut_market = pool.submit(_fetch_marketplace)

            try:
                spices_items = fut_spices.result(timeout=30)
                self.cache.upsert_many(spices_items)
                GLib.idle_add(self.main_window.set_loading_text,
                              f"Loaded {len(spices_items)} from Cinnamon Spices.")
            except Exception as e:
                log.warning(f"Spices fetch failed: {e}")

            try:
                remote_enhancements = fut_market.result(timeout=30)
                if remote_enhancements:
                    self.cache.upsert_many(remote_enhancements)
                    GLib.idle_add(self.main_window.set_loading_text,
                                  f"Loaded {len(remote_enhancements)} from marketplace.")
            except Exception as e:
                log.warning(f"Catalog fetch failed (will use local only): {e}")

        GLib.idle_add(self._init_done)

    @_async
    def start_init_local_only(self):
        GLib.idle_add(self.main_window.set_loading_text, "Scanning local enhancements...")
        local_items = self.scanner.scan_all()
        self.cache.upsert_many(local_items)
        GLib.idle_add(self.main_window.set_loading_text,
                      f"Found {len(local_items)} local enhancements. Loading catalog...")

        GLib.idle_add(self.main_window.set_loading_text, "Loading curated catalog...")
        try:
            seed_local()
        except Exception as e:
            log.warning(f"Seed catalog load failed: {e}")

        GLib.idle_add(self.main_window.set_loading_text, "Fetching Cinnamon Spices catalog...")
        try:
            spices_items = fetch_all_spices()
            self.cache.upsert_many(spices_items)
        except Exception as e:
            log.warning(f"Spices fetch failed: {e}")

        GLib.idle_add(self._init_done)

    def _init_done(self):
        self.main_window.navigate_to(PAGE_HOME)
        self.main_window.check_update_on_startup()

    @_async
    def refresh_catalog(self):
        if not self.api:
            return
        GLib.idle_add(self.main_window.show_progress, "Refreshing catalog...", 0.0)
        try:
            local_items = self.scanner.scan_all()
            self.cache.upsert_many(local_items)
            GLib.idle_add(self.main_window.show_progress, "Fetching Cinnamon Spices...", 0.3)
            try:
                spices_items = fetch_all_spices()
                self.cache.upsert_many(spices_items)
            except Exception as e:
                log.warning(f"Spices refresh failed: {e}")

            GLib.idle_add(self.main_window.show_progress, "Fetching remote catalog...", 0.6)

            result = self.api.list_enhancements(per_page=200)
            items = result.get("items", []) if isinstance(result, dict) else result
            remote = [Enhancement.from_api(item) for item in items]
            self.cache.upsert_many(remote)
            GLib.idle_add(self.main_window.show_progress, "Done!", 1.0)
        except Exception as e:
            log.warning(f"Refresh failed: {e}")
        GLib.idle_add(self._refresh_done)

    def _refresh_done(self):
        self.main_window.hide_progress()
        current = self.main_window.stack.get_visible_child_name()
        if current == "home":
            self.main_window._refresh_home()
        elif current == "browse":
            self.main_window._refresh_browse()

    def save_key(self, key: str):
        self._omni_key = key
        self.api = MintHubClient(key)
        self._save_key(key)

    def _save_key(self, key: str):
        config = self._load_config()
        config["omni_key"] = key
        CONFIG_FILE.write_text(json.dumps(config, indent=2))

    def _load_key(self) -> str:
        config = self._load_config()
        return config.get("omni_key", "")

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except Exception:
                pass
        return {}
