"""Auto-updater: checks GitHub releases and downloads/installs new .deb packages."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import requests

from constants import APP_VERSION

log = logging.getLogger("minthub")

GITHUB_REPO = "soccervortex/mint-hub"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_for_update() -> dict | None:
    try:
        resp = requests.get(RELEASES_URL, timeout=15,
                            headers={"Accept": "application/vnd.github.v3+json"})
        resp.raise_for_status()
        release = resp.json()
        tag = release.get("tag_name", "").lstrip("v")
        if not tag:
            return None
        if _version_tuple(tag) > _version_tuple(APP_VERSION):
            deb_url = ""
            deb_size = 0
            for asset in release.get("assets", []):
                if asset["name"].endswith(".deb"):
                    deb_url = asset["browser_download_url"]
                    deb_size = asset.get("size", 0)
                    break
            return {
                "version": tag,
                "current": APP_VERSION,
                "url": deb_url,
                "size": deb_size,
                "notes": release.get("body", ""),
                "html_url": release.get("html_url", ""),
            }
        return None
    except Exception as e:
        log.warning(f"Update check failed: {e}")
        return None


def download_and_install(deb_url: str, progress_cb=None) -> tuple[bool, str]:
    try:
        resp = requests.get(deb_url, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        tmpdir = tempfile.mkdtemp(prefix="minthub-update-")
        deb_path = os.path.join(tmpdir, "mint-hub-update.deb")

        with open(deb_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded / total)

        result = subprocess.run(
            ["pkexec", "dpkg", "-i", deb_path],
            capture_output=True, text=True, timeout=120,
        )

        os.unlink(deb_path)
        os.rmdir(tmpdir)

        if result.returncode == 0:
            return True, "Update installed successfully. Please restart the app."
        else:
            return False, f"Installation failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Installation timed out."
    except FileNotFoundError:
        return False, "pkexec not found. Install manually with: sudo dpkg -i <file>.deb"
    except Exception as e:
        return False, f"Update failed: {e}"


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0, 0, 0)
