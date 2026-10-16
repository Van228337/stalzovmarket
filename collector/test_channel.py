"""Channel & API Verification Script (Phase 0).

Tests network channel quality, Cloudflare reputation, rate limiting behavior,
and stale slice detection against EXBO STALCRAFT API.
Can run both locally and inside GitHub Actions.
"""

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("channel-test")

# Settings
DEFAULT_USER_AGENT = "stalcraft-market-bot/1.0 (Phase0-ChannelTest; contact: admin@stalzone.local)"
USER_AGENT = os.getenv("STALCRAFT_USER_AGENT", DEFAULT_USER_AGENT)
API_BASE = os.getenv("STALCRAFT_API_BASE_URL", "https://eapi.stalcraft.net")
DEMO_BASE = os.getenv("STALCRAFT_DEMO_API_BASE_URL", "https://dapi.stalcraft.net")
BACKUP_BASE = "https://eapi.stalzone.com"

CLIENT_ID = os.getenv("STALCRAFT_CLIENT_ID")
CLIENT_SECRET = os.getenv("STALCRAFT_CLIENT_SECRET")

# Public demo credentials from EXBO instructions
DEMO_CLIENT_ID = "1"
DEMO_CLIENT_SECRET = "E98cm6J9NNjTQopph0c2eIXNKafg4R1Cjz0TZh2D"


class ChannelTester:
    def __init__(self, rps: float = 4.0):
        self.rps = rps
        self.delay = 1.0 / rps
        self.stats = {
            "total_requests": 0,
            "status_200": 0,
            "status_400": 0,
            "status_401": 0,
            "status_403": 0,
            "status_404": 0,
            "status_429_1015": 0,
            "status_429_quota": 0,
            "status_5xx": 0,
            "other_status": 0,
            "stale_slices": 0,
            "transport_errors": 0,
        }

    def _get_headers(self, is_demo: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if is_demo:
            headers["Client-Id"] = DEMO_CLIENT_ID
            headers["Client-Secret"] = DEMO_CLIENT_SECRET
        elif CLIENT_ID and CLIENT_SECRET:
            headers["Client-Id"] = CLIENT_ID
            headers["Client-Secret"] = CLIENT_SECRET
        return headers

    async def test_regions(self, client: httpx.AsyncClient, base_url: str) -> bool:
        """Endpoint GET /regions requires no auth and tests basic Cloudflare connectivity."""
        url = f"{base_url}/regions"
        logger.info(f"Checking {url}...")
        try:
            self.stats["total_requests"] += 1
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
            logger.info(f"GET /regions status: {resp.status_code}")
            if resp.status_code == 200:
                self.stats["status_200"] += 1
                regions = resp.json()
                logger.info(f"Available regions: {regions}")
                return True
            elif resp.status_code == 403:
                self.stats["status_403"] += 1
                logger.warning(f"403 Forbidden on /regions! Cloudflare reputation or User-Agent issue.")
            else:
                self.stats["other_status"] += 1
                logger.warning(f"Unexpected status on /regions: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            self.stats["transport_errors"] += 1
            logger.error(f"Error accessing /regions: {e}")
        return False

    def is_stale_slice(self, lots: List[Dict[str, Any]], sort_key: str, order: str) -> bool:
        """Detector for Cloudflare stale slice anomaly.

        If order was requested as asc/desc on buyout_price or current_price,
        verify that items in response actually follow this order.
        """
        if len(lots) < 2:
            return False

        extracted = []
        for lot in lots:
            val = lot.get(sort_key)
            if val is not None:
                extracted.append(val)

        if len(extracted) < 2:
            return False

        if order == "asc":
            for i in range(len(extracted) - 1):
                if extracted[i] > extracted[i + 1]:
                    return True
        elif order == "desc":
            for i in range(len(extracted) - 1):
                if extracted[i] < extracted[i + 1]:
                    return True
        return False

    async def run_burst_test(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        endpoint_pattern: str,
        iterations: int = 50,
        is_demo: bool = False,
    ):
        """Run burst test to measure rate limiting and stale slices."""
        logger.info(f"Starting burst test: {iterations} requests at ~{self.rps} rps to {base_url}...")
        headers = self._get_headers(is_demo=is_demo)

        for i in range(iterations):
            start = time.perf_counter()
            self.stats["total_requests"] += 1
            try:
                # Alternate sorting parameters to test stale slice detector
                sort_key = "buyout_price" if i % 2 == 0 else "current_price"
                order = "asc" if (i // 2) % 2 == 0 else "desc"
                url = f"{base_url}{endpoint_pattern.format(sort=sort_key, order=order)}"

                resp = await client.get(url, headers=headers)
                status = resp.status_code

                if status == 200:
                    self.stats["status_200"] += 1
                    data = resp.json()
                    lots = data.get("lots", [])
                    if lots and self.is_stale_slice(lots, sort_key, order):
                        self.stats["stale_slices"] += 1
                        logger.warning(f"[{i+1}/{iterations}] Stale slice detected! Requested {sort_key} {order}")
                elif status == 400:
                    self.stats["status_400"] += 1
                elif status == 401:
                    self.stats["status_401"] += 1
                elif status == 403:
                    self.stats["status_403"] += 1
                    logger.warning(f"[{i+1}/{iterations}] HTTP 403 Forbidden")
                elif status == 429:
                    text = resp.text
                    if "1015" in text:
                        self.stats["status_429_1015"] += 1
                        logger.error(f"[{i+1}/{iterations}] Cloudflare IP rate limit 429 error 1015 hit!")
                    else:
                        self.stats["status_429_quota"] += 1
                        retry_after = resp.headers.get("Retry-After", "unknown")
                        logger.warning(f"[{i+1}/{iterations}] App quota 429 hit. Retry-After: {retry_after}")
                elif 500 <= status < 600:
                    self.stats["status_5xx"] += 1
                else:
                    self.stats["other_status"] += 1

            except Exception as e:
                self.stats["transport_errors"] += 1
                logger.error(f"[{i+1}/{iterations}] Request failed: {e}")

            elapsed = time.perf_counter() - start
            to_sleep = max(0.0, self.delay - elapsed)
            if to_sleep > 0:
                await asyncio.sleep(to_sleep)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i+1}/{iterations} completed. Status 200: {self.stats['status_200']}, 403: {self.stats['status_403']}, 429(1015): {self.stats['status_429_1015']}")

    def print_summary(self):
        total = self.stats["total_requests"]
        ok = self.stats["status_200"]
        success_rate = (ok / total * 100) if total > 0 else 0.0

        logger.info("=" * 60)
        logger.info("PHASE 0 CHANNEL TEST REPORT")
        logger.info("=" * 60)
        logger.info(f"Total Requests:     {total}")
        logger.info(f"HTTP 200 (Success): {ok} ({success_rate:.1f}%)")
        logger.info(f"HTTP 400 (Bad/Untradable): {self.stats['status_400']}")
        logger.info(f"HTTP 401 (Auth Required):  {self.stats['status_401']}")
        logger.info(f"HTTP 403 (Cloudflare block): {self.stats['status_403']}")
        logger.info(f"HTTP 429 Error 1015 (IP limit): {self.stats['status_429_1015']}")
        logger.info(f"HTTP 429 Quota (App rate):      {self.stats['status_429_quota']}")
        logger.info(f"Stale Slices Detected:          {self.stats['stale_slices']}")
        logger.info(f"Transport/Network Errors:       {self.stats['transport_errors']}")
        logger.info("=" * 60)

        passed = (
            self.stats["status_403"] == 0
            and self.stats["status_429_1015"] == 0
            and self.stats["transport_errors"] == 0
            and (ok > 0 or self.stats["status_401"] > 0)
        )
        if passed:
            logger.info("RESULT: PASS - Channel is viable for automated polling.")
        else:
            logger.warning("RESULT: WARN/FAIL - Issues detected on this channel.")
        return passed


async def main():
    tester = ChannelTester(rps=4.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    timeout = httpx.Timeout(15.0)

    client_id = os.getenv("STALCRAFT_CLIENT_ID")
    client_secret = os.getenv("STALCRAFT_CLIENT_SECRET")
    has_creds = bool(client_id and client_secret)

    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
        # Step 1: Check live production /regions
        has_eapi = await tester.test_regions(client, API_BASE)
        if not has_eapi:
            logger.info("Testing backup base URL...")
            await tester.test_regions(client, BACKUP_BASE)

        # Step 2: Burst test
        if has_creds:
            logger.info("Found production credentials! Testing live production STALCRAFT RU auction...")
            await tester.run_burst_test(
                client=client,
                base_url=API_BASE,
                endpoint_pattern="/RU/auction/1pyq/lots?limit=20&sort={sort}&order={order}&additional=true",
                iterations=25,
                is_demo=False,
            )
        else:
            logger.info("Testing Demo API auction endpoint with public credentials...")
            await tester.run_burst_test(
                client=client,
                base_url=DEMO_BASE,
                endpoint_pattern="/EU/auction/y1q9/lots?limit=20&sort={sort}&order={order}",
                iterations=40,
                is_demo=True,
            )

        tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
