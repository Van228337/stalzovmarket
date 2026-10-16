"""Production-ready asynchronous client for STALCRAFT EXBO API.

Implements all resilience rules from the specification:
- Explicit custom User-Agent
- Stale slice detection on auction responses
- Explicit discrimination between Cloudflare 429 (code 1015) and app quota 429 (Retry-After)
- Safe pagination up to total (max limit 200)
- Graceful error handling for both 400 formats
- Automatic fallback domain support
"""

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("stalcraft-client")


class CloudflareRateLimitError(Exception):
    """Raised when Cloudflare triggers Error 1015 (IP-level rate limit)."""
    pass


class AppQuotaRateLimitError(Exception):
    """Raised when EXBO application-level quota is exceeded."""
    def __init__(self, retry_after_sec: float):
        super().__init__(f"App quota exceeded. Retry-After: {retry_after_sec}s")
        self.retry_after_sec = retry_after_sec


class StaleSliceError(Exception):
    """Raised when Cloudflare silently returns an unsorted stale slice."""
    pass


class StalcraftClient:
    def __init__(
        self,
        base_url: str = "https://eapi.stalcraft.net",
        backup_url: str = "https://eapi.stalzone.com",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = "stalcraft-market-bot/1.0 (contact: admin@stalzone.local)",
        rate_limit_rps: float = 4.0,
        concurrency: int = 4,
        jitter_min_sec: float = 0.1,
        jitter_max_sec: float = 0.3,
        timeout_sec: float = 15.0,
        is_demo: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.backup_url = backup_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.rate_limit_rps = rate_limit_rps
        self.min_delay = 1.0 / rate_limit_rps
        self.jitter_min = jitter_min_sec
        self.jitter_max = jitter_max_sec
        self.is_demo = is_demo

        self._semaphore = asyncio.Semaphore(concurrency)
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        timeout = httpx.Timeout(timeout_sec)
        self._http = httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True)

    async def close(self):
        await self._http.aclose()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.is_demo:
            headers["Client-Id"] = "1"
            headers["Client-Secret"] = "E98cm6J9NNjTQopph0c2eIXNKafg4R1Cjz0TZh2D"
        elif self.client_id and self.client_secret:
            headers["Client-Id"] = self.client_id
            headers["Client-Secret"] = self.client_secret
        return headers

    async def _rate_limit_throttle(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            delay = self.min_delay + random.uniform(self.jitter_min, self.jitter_max)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            self._last_request_time = time.monotonic()

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_backup: bool = False,
    ) -> httpx.Response:
        base = self.backup_url if use_backup else self.base_url
        url = f"{base}{endpoint}"
        headers = self._get_headers()

        async with self._semaphore:
            await self._rate_limit_throttle()
            try:
                resp = await self._http.get(url, params=params, headers=headers)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if not use_backup and self.backup_url:
                    logger.warning(f"Connection failed on {base}, attempting backup {self.backup_url}: {e}")
                    return await self._request(endpoint, params=params, use_backup=True)
                raise

        # Check response codes per Section 7
        if resp.status_code == 429:
            body = resp.text
            if "1015" in body:
                logger.error("Cloudflare Rate Limit (error 1015) encountered!")
                raise CloudflareRateLimitError("Cloudflare IP rate limit 1015")
            else:
                retry_header = resp.headers.get("Retry-After", "10")
                try:
                    retry_sec = float(retry_header)
                except ValueError:
                    retry_sec = 10.0
                logger.warning(f"App quota limit reached. Retry-After: {retry_sec}s")
                raise AppQuotaRateLimitError(retry_sec)

        return resp

    def check_stale_slice(
        self,
        lots: List[Dict[str, Any]],
        sort_key: Optional[str],
        order: Optional[str],
    ) -> bool:
        """Detect Cloudflare stale slice anomaly.

        If order was explicitly requested, ensure lots adhere to that ordering.
        """
        if not sort_key or not order or len(lots) < 2:
            return False

        vals = []
        for lot in lots:
            val = lot.get(sort_key)
            if val is not None:
                vals.append(val)

        if len(vals) < 2:
            return False

        if order.lower() == "asc":
            for i in range(len(vals) - 1):
                if vals[i] > vals[i + 1]:
                    return True
        elif order.lower() == "desc":
            for i in range(len(vals) - 1):
                if vals[i] < vals[i + 1]:
                    return True
        return False

    async def get_regions(self) -> List[Dict[str, Any]]:
        """GET /regions - list supported regions."""
        resp = await self._request("/regions")
        if resp.status_code == 200:
            return resp.json()
        resp.raise_for_status()
        return []

    async def get_auction_lots(
        self,
        region: str,
        item_id: str,
        limit: int = 20,
        offset: int = 0,
        sort: Optional[str] = "buyout_price",
        order: Optional[str] = "asc",
        additional: bool = False,
    ) -> Tuple[int, List[Dict[str, Any]], bool]:
        """GET /{region}/auction/{item}/lots.

        Returns:
            (total_count, lots_list, is_stale_slice)
        """
        limit = min(200, max(1, limit))
        endpoint = f"/{region}/auction/{item_id}/lots"
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order
        if additional:
            params["additional"] = "true"

        resp = await self._request(endpoint, params=params)

        if resp.status_code == 400:
            # 400 on auction endpoint may mean item is non-tradable
            logger.info(f"Item {item_id} returned 400 on lots endpoint (non-tradable or bad params).")
            return 0, [], False

        resp.raise_for_status()
        data = resp.json()
        total = int(data.get("total", 0))
        lots = data.get("lots", [])

        stale = self.check_stale_slice(lots, sort_key=sort, order=order)
        return total, lots, stale

    async def get_auction_history(
        self,
        region: str,
        item_id: str,
        limit: int = 200,
        offset: int = 0,
        additional: bool = False,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """GET /{region}/auction/{item}/history.

        Returns:
            (total_count, prices_list)
        """
        limit = min(200, max(1, limit))
        endpoint = f"/{region}/auction/{item_id}/history"
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if additional:
            params["additional"] = "true"

        resp = await self._request(endpoint, params=params)

        if resp.status_code == 400:
            logger.info(f"Item {item_id} returned 400 on history endpoint (non-tradable).")
            return 0, []

        resp.raise_for_status()
        data = resp.json()
        total = int(data.get("total", 0))
        prices = data.get("prices", [])
        return total, prices
