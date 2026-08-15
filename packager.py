"""Create .tar.gz enhancement packages from local files."""

import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path


def create_package(source_dir: str, manifest: dict,
                   thumbnail_path: str = "", output_path: str = "") -> str:
    source = Path(source_dir)
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    errors = validate_manifest(manifest)
    if errors:
        raise ValueError(f"Invalid manifest: {'; '.join(errors)}")

    slug = manifest["slug"]
    version = manifest.get("version", "1.0.0")

    if not output_path:
        output_path = str(Path.home() / f"{slug}-{version}.tar.gz")

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / slug
        pkg_dir.mkdir()

        (pkg_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        if thumbnail_path and Path(thumbnail_path).exists():
            shutil.copy2(thumbnail_path, pkg_dir / "thumbnail.png")

        content_dir = pkg_dir / manifest.get("name", slug)
        shutil.copytree(source, content_dir)

        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(str(pkg_dir), arcname=slug)

    return output_path


def validate_manifest(manifest: dict) -> list:
    errors = []
    required = ["slug", "name", "category"]
    for field in required:
        if not manifest.get(field):
            errors.append(f"Missing required field: {field}")

    valid_categories = {
        "gtk-theme", "cinnamon-theme", "icon-theme", "cursor-theme",
        "wallpaper", "wallpaper-pack", "applet", "desklet", "extension",
        "font", "sound-theme", "conky", "script", "fix", "grub-theme",
        "plymouth-theme",
    }
    cat = manifest.get("category", "")
    if cat and cat not in valid_categories:
        errors.append(f"Invalid category: {cat}")

    return errors


def generate_manifest_template(category: str) -> dict:
    return {
        "slug": "",
        "name": "",
        "version": "1.0.0",
        "author": "",
        "category": category,
        "summary": "",
        "description": "",
        "tags": [],
        "license": "GPL-3.0",
        "homepage": "",
        "install_path": "",
        "apply_command": "",
        "revert_command": "",
    }
