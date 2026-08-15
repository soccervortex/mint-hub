"""Fetch enhancement data from Cinnamon Spices (spices.linuxmint.com)."""

from datetime import datetime

import requests

from enhancement import Enhancement

SPICES_BASE = "https://cinnamon-spices.linuxmint.com"

SPICES_FEEDS = {
    "applet":    f"{SPICES_BASE}/json/applets.json",
    "desklet":   f"{SPICES_BASE}/json/desklets.json",
    "extension": f"{SPICES_BASE}/json/extensions.json",
    "cinnamon-theme": f"{SPICES_BASE}/json/themes.json",
}


def fetch_spices(category: str) -> list[Enhancement]:
    url = SPICES_FEEDS.get(category)
    if not url:
        return []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Spices fetch failed for {category}: {e}")
        return []

    results = []
    for uuid, item in data.items():
        e = Enhancement()
        e.slug = f"spices-{category}-{uuid}"
        e.name = item.get("name", uuid)
        e.category = category
        e.summary = _truncate(item.get("description", ""), 200)
        e.description = item.get("description", "")
        e.author = item.get("author_user", "")
        e.score = float(item.get("score", 0))
        e.avg_rating = min(5.0, e.score / 20) if e.score > 0 else 0.0
        e.file_size = item.get("file_size", 0)
        e.source = "spices"
        e.status = "published"
        e.installed = False
        e.writable = True

        e.download_url = f"{SPICES_BASE}{item['file']}" if item.get("file") else ""

        if item.get("icon"):
            e.thumbnail_url = f"{SPICES_BASE}{item['icon']}"
        elif item.get("screenshot"):
            e.thumbnail_url = f"{SPICES_BASE}{item['screenshot']}"

        if item.get("screenshot"):
            e.screenshots = [f"{SPICES_BASE}{item['screenshot']}"]

        created = item.get("created")
        if created:
            try:
                e.created_at = datetime.fromtimestamp(created).isoformat()
            except (OSError, ValueError):
                pass

        edited = item.get("last_edited")
        if edited:
            try:
                e.updated_at = datetime.fromtimestamp(edited).isoformat()
            except (OSError, ValueError):
                pass

        results.append(e)

    return results


def fetch_all_spices() -> list[Enhancement]:
    all_items = []
    for category in SPICES_FEEDS:
        items = fetch_spices(category)
        all_items.extend(items)
        print(f"  Spices: {len(items)} {category}s")
    return all_items


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
