"""Main Collector & Analytics Orchestrator.

Strictly adheres to Patch 1 (Watchlist) and Patch 2 (Names only):
- Only polls items explicitly enabled in watchlist (NEVER whole catalog)
- Respects individual item threshold overrides (min_roi, min_profit, max_buy_unit)
- Filters weapon modules (1pyq) based on user-defined slot / potential filters
- Identifies untradable items on HTTP 400
- Generates compact digest.json for LLM analyst
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from collector.client import StalcraftClient, CloudflareRateLimitError, AppQuotaRateLimitError
from collector.items_db import ItemsDatabase
from collector.fingerprint import compute_lot_fingerprint, compute_sale_hash, match_disappeared_lot
from collector.notifier import TelegramNotifier
from analytics.pricing import SaleRecord, compute_fair_price_metrics
from analytics.signals import ActiveLot, calculate_signal, TradeSignal
from analytics.digest import build_market_digest, export_digest_json
from analytics.modules import parse_weapon_module
from analytics.segmentation import get_item_segment
from analytics.export_for_llm import export_llm_bundle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("collector-runner")


def compute_filters_hash(filters: Dict[str, Any]) -> str:
    """Compute normalized SHA256 hash for multi-module subscription filters (Patch 2 Section 4)."""
    if not filters:
        return ""
    norm = json.dumps(filters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


class CollectorRunner:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.market_cfg = self.config.get("market", {})
        self.collector_cfg = self.config.get("collector", {})
        self.region = os.getenv("STALCRAFT_REGION", self.market_cfg.get("region", "RU"))

        client_id = os.getenv("STALCRAFT_CLIENT_ID")
        client_secret = os.getenv("STALCRAFT_CLIENT_SECRET")
        is_demo = not bool(client_id and client_secret)

        target_base_url = (
            self.market_cfg.get("demo_url", "https://dapi.stalcraft.net")
            if is_demo
            else self.market_cfg.get("base_url", "https://eapi.stalcraft.net")
        )

        logger.info(f"Initialized client. Mode={'DEMO' if is_demo else 'PROD'}, BaseURL={target_base_url}")

        self.client = StalcraftClient(
            base_url=target_base_url,
            backup_url=self.market_cfg.get("backup_base_url", "https://eapi.stalzone.com"),
            client_id=client_id,
            client_secret=client_secret,
            user_agent=self.collector_cfg.get("user_agent", "stalcraft-market-bot/1.0"),
            rate_limit_rps=float(self.collector_cfg.get("rate_limit_rps", 4.0)),
            concurrency=int(self.collector_cfg.get("concurrency", 4)),
            jitter_min_sec=float(self.collector_cfg.get("jitter_min_sec", 0.1)),
            jitter_max_sec=float(self.collector_cfg.get("jitter_max_sec", 0.3)),
            is_demo=is_demo,
        )

        realm = "ru" if self.region.upper() == "RU" else "global"
        self.items_db = ItemsDatabase(realm=realm)

        self.metrics = {
            "requests": 0,
            "ok": 0,
            "http_400": 0,
            "http_401": 0,
            "http_403": 0,
            "http_429_1015": 0,
            "http_429_quota": 0,
            "stale_slices": 0,
            "retries": 0,
        }

    async def initialize(self):
        await self.items_db.load_catalog()

    def get_tracked_watchlist(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract enabled watchlist items from config.yaml (Patch 1 Section 5.2)."""
        raw_list = self.config.get("watchlist", [])
        tracked = []
        for entry in raw_list:
            if isinstance(entry, str):
                entry_dict = {"item_id": entry, "enabled": True, "filters": {}, "tier": "hot"}
            elif isinstance(entry, dict):
                entry_dict = entry
            else:
                continue

            if not entry_dict.get("enabled", True):
                continue

            item_tier = entry_dict.get("tier", "hot")
            if tier and tier != "all" and item_tier != tier:
                continue

            tracked.append(entry_dict)
        return tracked

    async def run_cycle(
        self,
        watchlist_override: Optional[List[Dict[str, Any]]] = None,
        dry_run: bool = False,
        tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute one complete data collection and signal generation cycle."""
        start_time = datetime.now(timezone.utc)
        logger.info(f"Starting collector cycle for region={self.region}, dry_run={dry_run}, tier={tier or 'all'}...")

        # Watchlist rule (Patch 1 Section 5.2 & 10.4): ONLY poll tracked items
        watchlist = watchlist_override if watchlist_override is not None else self.get_tracked_watchlist(tier=tier)
        logger.info(f"Active watchlist items to poll: {[w['item_id'] for w in watchlist]}")

        all_signals: List[TradeSignal] = []
        avoid_list: List[Dict[str, str]] = []

        for entry in watchlist:
            item_id = entry.get("item_id")
            if not item_id:
                continue

            item_meta = self.items_db.items.get(item_id, {})
            filters = entry.get("filters", {})
            is_module = (item_id == "1pyq")

            # 1. Fetch active auction lots (always request additional=True to inspect qlt, ptn, etc.)
            self.metrics["requests"] += 1
            try:
                total_lots, raw_lots, is_stale = await self.client.get_auction_lots(
                    region=self.region,
                    item_id=item_id,
                    limit=50,
                    sort="buyout_price",
                    order="asc",
                    additional=True,
                )
                self.metrics["ok"] += 1

                if is_stale:
                    self.metrics["stale_slices"] += 1
                    logger.warning(f"Discarding stale slice for {item_id}")
                    raw_lots = []
            except CloudflareRateLimitError:
                self.metrics["http_429_1015"] += 1
                logger.error("Cloudflare rate limit 1015 encountered, aborting cycle.")
                break
            except Exception as e:
                logger.error(f"Error fetching lots for {item_id}: {e}")
                continue

            # 2. Fetch sales history (always request additional=True to segment by rarity and upgrade)
            self.metrics["requests"] += 1
            try:
                total_history, raw_prices = await self.client.get_auction_history(
                    region=self.region,
                    item_id=item_id,
                    limit=200,
                    additional=True,
                )
                self.metrics["ok"] += 1
            except Exception as e:
                logger.error(f"Error fetching history for {item_id}: {e}")
                raw_prices = []

            # 3. Parse sales records and group strictly by segment_key
            sales_by_segment: Dict[str, List[SaleRecord]] = {}
            for p in raw_prices:
                time_str = p.get("time")
                try:
                    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00")) if time_str else datetime.now(timezone.utc)
                except ValueError:
                    dt = datetime.now(timezone.utc)

                add = p.get("additional")
                if is_module and add:
                    parsed_mod = parse_weapon_module(add)
                    seg_key = parsed_mod.segment_key
                else:
                    seg_key, _ = get_item_segment(item_id, item_meta, add)

                sr = SaleRecord(
                    amount=int(p.get("amount", 1)),
                    price=int(p.get("price", 0)),
                    sold_at=dt,
                    additional=add,
                    segment_key=seg_key,
                )
                sales_by_segment.setdefault(seg_key, []).append(sr)

            # 4. Parse active lots and group by segment_key
            lots_by_segment: Dict[str, List[ActiveLot]] = {}
            for lot_dict in raw_lots:
                amount = int(lot_dict.get("amount", 1))
                buyout = int(lot_dict.get("buyoutPrice", 0))
                additional = lot_dict.get("additional")

                if is_module and additional:
                    parsed_mod = parse_weapon_module(additional)
                    seg_key = parsed_mod.segment_key
                    seg_label = "Модуль"

                    # Check module filters
                    if filters:
                        min_pot = float(filters.get("min_potential", 0))
                        req_add_on = filters.get("add_on")
                        req_dev = filters.get("deviation")
                        req_concept = filters.get("concept")

                        skip_lot = False
                        for roll in parsed_mod.rolls:
                            if roll.slot_id == 0 and req_add_on and roll.definition_id != req_add_on:
                                skip_lot = True
                            if roll.slot_id == 1 and req_dev and roll.definition_id != req_dev:
                                skip_lot = True
                            if roll.slot_id == 2 and req_concept and roll.definition_id != req_concept:
                                skip_lot = True
                            if roll.potential < min_pot:
                                skip_lot = True
                        if skip_lot:
                            continue
                else:
                    seg_key, seg_label = get_item_segment(item_id, item_meta, additional)

                active_lot = ActiveLot(
                    id=None,
                    item_id=item_id,
                    region=self.region,
                    amount=amount,
                    start_price=int(lot_dict.get("startPrice", 0)),
                    current_price=int(lot_dict.get("currentPrice", 0)),
                    buyout_price=buyout,
                    start_time=None,
                    end_time=None,
                    additional=additional,
                    qlt=int(additional.get("qlt", 0)) if additional else 0,
                    segment_key=seg_key,
                    segment_label=seg_label,
                )
                lots_by_segment.setdefault(seg_key, []).append(active_lot)

            # 5. Strategy config with individual item overrides
            merged_config = dict(self.config)
            strat = dict(merged_config.get("strategy", {}))
            if entry.get("min_roi") is not None:
                strat["min_roi"] = float(entry["min_roi"])
            if entry.get("min_profit_abs") is not None:
                strat["min_profit_abs"] = float(entry["min_profit_abs"])
            merged_config["strategy"] = strat

            # 6. Evaluate signals strictly PER SEGMENT (never cross-comparing different rarities or upgrades!)
            for seg_key, seg_lots in lots_by_segment.items():
                seg_sales = sales_by_segment.get(seg_key, [])
                if len(seg_sales) < 5:
                    logger.debug(f"Skipping {item_id} [{seg_key}]: only {len(seg_sales)} sales in sample (need >= 5)")
                    continue

                metrics = compute_fair_price_metrics(seg_sales, half_life_days=2.0)
                if not metrics:
                    continue

                if metrics.is_spike:
                    avoid_list.append({
                        "item_id": item_id,
                        "reason": f"Сегмент [{seg_key}] имеет ценовой всплеск/манипуляцию (рост x{metrics.trend_ratio:.2f}).",
                    })
                    continue

                for lot in seg_lots:
                    signal = calculate_signal(
                        lot=lot,
                        metrics=metrics,
                        active_lots_in_segment=seg_lots,
                        config=merged_config,
                    )
                    if signal:
                        all_signals.append(signal)

        # 6. Generate compact digest.json (Patch 1 Section 6.5)
        digest = build_market_digest(
            region=self.region,
            signals=all_signals,
            items_meta=self.items_db.items,
            avoid_list=avoid_list,
            config=self.config,
            data_freshness_minutes=10.0,
            tracked_items_count=len(watchlist),
        )

        os.makedirs("data", exist_ok=True)
        export_digest_json(digest, "data/digest.json")
        for web_dir in ["web", "docs"]:
            if os.path.exists(web_dir):
                export_digest_json(digest, f"{web_dir}/digest.json")
        logger.info(f"Digest exported to data/digest.json with {len(all_signals)} opportunities from watchlist.")

        # Export ready-to-paste bundle for external LLMs (ChatGPT / Claude / DeepSeek)
        export_llm_bundle(
            digest_path="data/digest.json",
            prompt_path="prompts/llm_analyst.md",
            output_path="data/prompt_for_external_llm.txt",
        )

        # Dispatch Telegram alerts if enabled
        alerts_cfg = self.config.get("alerts", {})
        if alerts_cfg.get("telegram_enabled", False):
            notifier = TelegramNotifier()
            for opp in digest.get("top_opportunities", [])[:3]:
                if opp.get("confidence", 0) >= alerts_cfg.get("min_signal_score_to_alert", 0.70):
                    try:
                        await notifier.notify_signal(opp)
                    except Exception as e:
                        logger.warning(f"Telegram dispatch failed: {e}")

        finished_time = datetime.now(timezone.utc)
        duration_sec = (finished_time - start_time).total_seconds()
        logger.info(f"Cycle completed in {duration_sec:.1f}s. Requests={self.metrics['requests']}, Ok={self.metrics['ok']}, Stale={self.metrics['stale_slices']}")

        await self.client.close()
        return {
            "signals_count": len(all_signals),
            "requests": self.metrics["requests"],
            "duration_sec": duration_sec,
        }


def main():
    parser = argparse.ArgumentParser(description="STALCRAFT Market Watchlist Runner")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Run in dry-run mode")
    parser.add_argument("--tier", type=str, default="hot", choices=["hot", "warm", "all"], help="Item tier to process (default: hot)")
    args = parser.parse_args()

    runner = CollectorRunner()
    asyncio.run(runner.initialize())
    asyncio.run(runner.run_cycle(dry_run=args.dry_run, tier=args.tier))


if __name__ == "__main__":
    main()
