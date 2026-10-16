"""Catalog loader and search indexer for STALCRAFT items.

Merges official EXBO listing.json with catalog_overrides.json.
Generates web/catalog.json for client-side search without exposing raw IDs in UI.
Normalizes text (ё -> е, lowercase, no special quotes) for fast search.
"""

import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("items-db")

DEFAULT_REPO_BASE = "https://raw.githubusercontent.com/EXBO-Studio/stalcraft-database/main"


def normalize_search_text(text: str) -> str:
    """Normalize text for insensitive search: lowercase, ё -> е, strip quotes/punctuation."""
    if not text:
        return ""
    cleaned = text.lower().replace("ё", "е")
    cleaned = re.sub(r'["«»„“\',.\-_/\\()\[\]]', " ", cleaned)
    return " ".join(cleaned.split())


class ItemsDatabase:
    def __init__(
        self,
        repo_base: str = DEFAULT_REPO_BASE,
        cache_dir: str = "cache",
        overrides_path: str = "catalog_overrides.json",
        realm: str = "ru",
    ):
        self.repo_base = repo_base.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.overrides_path = Path(overrides_path)
        self.realm = realm.lower()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.items: Dict[str, Dict[str, Any]] = {}

    def _get_cache_path(self) -> Path:
        return self.cache_dir / f"listing_{self.realm}.json"

    def _load_overrides(self) -> List[Dict[str, Any]]:
        if not self.overrides_path.exists():
            return []
        try:
            with open(self.overrides_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read catalog overrides from {self.overrides_path}: {e}")
            return []

    async def load_catalog(
        self,
        client: Optional[httpx.AsyncClient] = None,
        force_refresh: bool = False,
        export_web_catalog: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Load listing.json, apply overrides, and optionally export web/catalog.json."""
        cache_file = self._get_cache_path()
        raw_list = None

        if cache_file.exists() and not force_refresh:
            logger.info(f"Loading items catalog from cache: {cache_file}")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")

        if raw_list is None:
            url = f"{self.repo_base}/{self.realm}/listing.json"
            logger.info(f"Fetching listing.json from {url}...")

            close_client = False
            if client is None:
                client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
                close_client = True

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                raw_list = resp.json()

                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(raw_list, f, ensure_ascii=False)
            finally:
                if close_client:
                    await client.aclose()

        # Parse EXBO catalog
        self.items = self._parse_listing(raw_list)

        # Merge catalog_overrides.json (Patch 2 Section 5)
        overrides = self._load_overrides()
        for o in overrides:
            o_id = o.get("id")
            if not o_id:
                continue

            if o_id in self.items:
                logger.warning(f"Override conflict: item_id '{o_id}' already exists in EXBO catalog. Official catalog takes precedence.")
                continue

            name_ru = o.get("name_ru", o_id)
            name_en = o.get("name_en", o_id)
            self.items[o_id] = {
                "item_id": o_id,
                "name_ru": name_ru,
                "name_en": name_en,
                "category": o.get("category", "misc"),
                "rank": o.get("rank", "DEFAULT"),
                "icon_path": o.get("icon", ""),
                "listing_path": f"/overrides/{o_id}.json",
                "source": "manual_override",
                "search_text": normalize_search_text(f"{name_ru} {name_en}"),
            }

        logger.info(f"Total catalog items available: {len(self.items)} (including overrides).")

        if export_web_catalog:
            self.export_catalog_json()

        return self.items

    def _parse_listing(self, raw_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        parsed = {}
        for entry in raw_list:
            data_path = entry.get("data", "")
            if not data_path:
                continue

            filename = os.path.basename(data_path)
            item_id = os.path.splitext(filename)[0]

            name_obj = entry.get("name", {})
            name_lines = name_obj.get("lines", {}) if isinstance(name_obj, dict) else {}

            name_ru = name_lines.get("ru")
            if not name_ru and isinstance(name_obj, dict):
                name_ru = name_obj.get("text")

            name_en = name_lines.get("en", item_id)

            parts = [p for p in data_path.strip("/").split("/") if p not in ("items", filename)]
            category = "/".join(parts) if parts else "misc"

            display_name_ru = name_ru or item_id
            search_str = f"{display_name_ru} {name_en}"

            parsed[item_id] = {
                "item_id": item_id,
                "name_ru": display_name_ru,
                "name_en": name_en or item_id,
                "category": category,
                "rank": entry.get("color", "DEFAULT"),
                "icon_path": entry.get("icon", ""),
                "listing_path": data_path,
                "source": "exbo",
                "search_text": normalize_search_text(search_str),
            }
        return parsed

    def export_catalog_json(self, target_path: str = "web/catalog.json"):
        """Export compact catalog JSON for static web frontend search."""
        compact_list = []
        for item in self.items.values():
            compact_list.append({
                "item_id": item["item_id"], # used internally by frontend selection
                "name_ru": item["name_ru"],
                "name_en": item["name_en"],
                "category": item["category"],
                "rank": item["rank"],
                "icon_path": item["icon_path"],
                "source": item.get("source", "exbo"),
                "search_text": item["search_text"],
            })

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(compact_list, f, ensure_ascii=False)
        logger.info(f"Exported {len(compact_list)} catalog items to {target_path}.")

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.items.get(item_id)
