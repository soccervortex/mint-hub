#!/usr/bin/env python3
"""Seed the Mint Hub marketplace with curated starter content.

Usage:
    python3 seeder.py <omni_key>
    python3 seeder.py --local-only   # seed local cache without uploading
"""

import json
import sys
from pathlib import Path

from api_client import MintHubClient
from enhancement import Enhancement
from local_cache import LocalCache

CATALOG_PATH = Path(__file__).parent / "seed_catalog.json"


def load_catalog() -> list[dict]:
    return json.loads(CATALOG_PATH.read_text())


def seed_remote(omni_key: str):
    catalog = load_catalog()
    client = MintHubClient(omni_key)

    print(f"Seeding {len(catalog)} enhancements to Mint Hub...")
    success = 0
    for item in catalog:
        try:
            client.upload(item)
            print(f"  + {item['slug']} ({item['category']})")
            success += 1
        except Exception as e:
            print(f"  x {item['slug']}: {e}")

    print(f"\nDone: {success}/{len(catalog)} uploaded.")
    client.close()


def seed_local():
    catalog = load_catalog()
    cache = LocalCache()

    print(f"Seeding {len(catalog)} enhancements to local cache...")
    for item in catalog:
        e = Enhancement()
        e.slug = item["slug"]
        e.name = item["name"]
        e.category = item["category"]
        e.version = item.get("version", "1.0.0")
        e.author = item.get("author", "")
        e.summary = item.get("summary", "")
        e.description = item.get("description", "")
        e.license = item.get("license", "GPL-3.0")
        e.tags = item.get("tags", [])
        e.featured = item.get("featured", False)
        e.source = "minthub"
        e.status = "published"
        e.score = 100.0 if e.featured else 50.0
        cache.upsert(e)
        print(f"  + {e.slug} ({e.category})")

    cache.close()
    print(f"\nDone: {len(catalog)} seeded to local cache.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--local-only":
        seed_local()
    else:
        seed_remote(sys.argv[1])
