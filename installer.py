"""Download, extract, install, and uninstall enhancements."""

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

import requests

from constants import INSTALL_PATHS, CACHE_DIR, DOWNLOAD_DIR, THUMBNAIL_CACHE_DIR
from enhancement import Enhancement
from local_cache import LocalCache
from safety_scanner import scan_archive, ScanResult

log = logging.getLogger("minthub")


class EnhancementInstaller:
    def __init__(self, cache: LocalCache):
        self._cache = cache
        self._last_scan = None
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def last_scan_result(self) -> ScanResult | None:
        return self._last_scan

    def install_from_url(self, enh: Enhancement, download_url: str,
                         progress_cb=None) -> bool:
        suffix = ".zip" if download_url.endswith(".zip") else ".tar.gz"
        archive_path = DOWNLOAD_DIR / f"{enh.slug}{suffix}"
        try:
            resp = requests.get(download_url, stream=True, timeout=120)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(archive_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(downloaded / total)
            scan = scan_archive(str(archive_path))
            if not scan.safe:
                self._last_scan = scan
                log.warning(f"Safety scan BLOCKED install of {enh.slug}:\n{scan.summary}")
                return False
            self._last_scan = scan
            return self.install_from_archive(enh, archive_path)
        except Exception as e:
            log.warning(f"Install failed for {enh.slug}: {e}")
            return False
        finally:
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)

    def install_from_archive(self, enh: Enhancement, archive_path: Path) -> bool:
        category = enh.category
        base_dir = INSTALL_PATHS.get(category)
        if not base_dir:
            return False
        base_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                if zipfile.is_zipfile(str(archive_path)):
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extractall(tmpdir)
                else:
                    with tarfile.open(archive_path, "r:*") as tar:
                        tar.extractall(tmpdir, filter="data")
            except Exception as e:
                log.warning(f"Extract failed: {e}")
                return False

            tmp = Path(tmpdir)
            contents = list(tmp.iterdir())
            if not contents:
                return False

            source = contents[0] if len(contents) == 1 and contents[0].is_dir() else tmp

            if category in ("wallpaper", "wallpaper-pack"):
                return self._install_wallpapers(enh, source, base_dir)
            elif category == "font":
                return self._install_fonts(enh, source, base_dir)
            else:
                return self._install_directory(enh, source, base_dir)

    def _install_directory(self, enh: Enhancement, source: Path, base_dir: Path) -> bool:
        dest = base_dir / enh.name
        if dest.exists():
            shutil.rmtree(dest)
        try:
            shutil.copytree(source, dest)
            enh.install_path = str(dest)
            enh.installed = True
            enh.installed_version = enh.version
            self._cache.mark_installed(enh.slug, enh.version, str(dest))
            self._post_install(enh)
            return True
        except Exception as e:
            log.warning(f"Copy failed: {e}")
            return False

    def _install_wallpapers(self, enh: Enhancement, source: Path, base_dir: Path) -> bool:
        from constants import IMAGE_EXTENSIONS
        installed = False
        for f in source.rglob("*"):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                dest = base_dir / f.name
                shutil.copy2(f, dest)
                if not installed:
                    enh.install_path = str(dest)
                installed = True
        if installed:
            enh.installed = True
            enh.installed_version = enh.version
            self._cache.mark_installed(enh.slug, enh.version, enh.install_path)
        return installed

    def _install_fonts(self, enh: Enhancement, source: Path, base_dir: Path) -> bool:
        from constants import FONT_EXTENSIONS
        installed = False
        for f in source.rglob("*"):
            if f.is_file() and f.suffix.lower() in FONT_EXTENSIONS:
                dest = base_dir / f.name
                shutil.copy2(f, dest)
                if not installed:
                    enh.install_path = str(base_dir)
                installed = True
        if installed:
            enh.installed = True
            enh.installed_version = enh.version
            self._cache.mark_installed(enh.slug, enh.version, str(base_dir))
            subprocess.run(["fc-cache", "-f", str(base_dir)], capture_output=True, timeout=30)
        return installed

    def _post_install(self, enh: Enhancement):
        if enh.category == "icon-theme":
            icon_dir = Path(enh.install_path)
            subprocess.run(["gtk-update-icon-cache", str(icon_dir)],
                           capture_output=True, timeout=30)

    def uninstall(self, enh: Enhancement) -> bool:
        if not enh.install_path or not enh.writable:
            return False
        path = Path(enh.install_path)
        if not path.exists():
            self._cache.mark_uninstalled(enh.slug)
            return True
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self._cache.mark_uninstalled(enh.slug)
            enh.installed = False
            enh.installed_version = ""
            return True
        except Exception as e:
            log.warning(f"Uninstall failed: {e}")
            return False

    def download_thumbnail(self, url: str, slug: str) -> str:
        cache_path = THUMBNAIL_CACHE_DIR / f"{slug}.png"
        if cache_path.exists():
            return str(cache_path)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
            return str(cache_path)
        except Exception:
            return ""
