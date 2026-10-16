"""Supabase Cloud Database Synchronization Client.

Performs asynchronous batch upserts of:
- items (catalog entries)
- lots (active auction listings)
- sales (completed transactions)
- signals (generated arbitrage opportunities)
- price_rollups (hourly market snapshots)

Uses direct HTTP PostgREST API with service_role key (bypasses RLS, zero external heavy dependencies).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("supabase-sync")


class SupabaseSync:
    def __init__(
        self,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
    ):
        self.url = (supabase_url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.key = service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        self.enabled = bool(self.url and self.key)

        if not self.enabled:
            logger.info("Supabase credentials not configured. Running in file-based storage mode.")
        else:
            logger.info(f"Supabase sync initialized for: {self.url}")

    def _headers(self, prefer: str = "resolution=merge-duplicates") -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    async def upsert_items(self, items: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not items:
            return False
        endpoint = f"{self.url}/rest/v1/items"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=items, headers=self._headers())
                if resp.status_code in (200, 201):
                    logger.info(f"Synced {len(items)} items to Supabase.")
                    return True
                else:
                    logger.warning(f"Supabase items sync error {resp.status_code}: {resp.text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"Supabase items sync failed: {e}")
            return False

    async def upsert_lots(self, lots: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not lots:
            return False
        endpoint = f"{self.url}/rest/v1/lots"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=lots, headers=self._headers("resolution=merge-duplicates"))
                if resp.status_code in (200, 201):
                    logger.info(f"Synced {len(lots)} active lots to Supabase.")
                    return True
                else:
                    logger.warning(f"Supabase lots sync error {resp.status_code}: {resp.text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"Supabase lots sync failed: {e}")
            return False

    async def insert_sales(self, sales: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not sales:
            return False
        endpoint = f"{self.url}/rest/v1/sales"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=sales, headers=self._headers("resolution=ignore-duplicates"))
                if resp.status_code in (200, 201):
                    logger.info(f"Synced {len(sales)} sales to Supabase.")
                    return True
                else:
                    logger.warning(f"Supabase sales sync error {resp.status_code}: {resp.text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"Supabase sales sync failed: {e}")
            return False

    async def insert_signals(self, signals: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not signals:
            return False
        endpoint = f"{self.url}/rest/v1/signals"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=signals, headers=self._headers())
                if resp.status_code in (200, 201):
                    logger.info(f"Synced {len(signals)} signals to Supabase.")
                    return True
                else:
                    logger.warning(f"Supabase signals sync error {resp.status_code}: {resp.text[:200]}")
                    return False
        except Exception as e:
            logger.warning(f"Supabase signals sync failed: {e}")
            return False
