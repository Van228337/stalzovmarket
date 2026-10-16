"""Compact market digest generator (Section 11.1).

Produces digest.json (≤ 30-60 KB) optimized for consumption by LLM prompts.
All prices are per unit, timestamps in UTC.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from analytics.signals import TradeSignal


def build_market_digest(
    region: str,
    signals: List[TradeSignal],
    items_meta: Dict[str, Dict[str, Any]],
    avoid_list: List[Dict[str, str]],
    config: Dict[str, Any],
    data_freshness_minutes: float = 12.0,
    tracked_items_count: int = 150,
    turnover_24h: float = 0.0,
    positions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble structured, compact market digest dictionary."""
    econ = config.get("economics", {})
    strat = config.get("strategy", {})

    # Sort signals by score descending
    sorted_signals = sorted(signals, key=lambda s: s.score, reverse=True)

    top_opportunities = []
    for s in sorted_signals[:25]:  # Top 25 deals to keep payload compact (~30 KB)
        meta = items_meta.get(s.item_id, {})
        name_ru = meta.get("name_ru", s.item_id)

        opportunity = {
            "item_id": s.item_id,
            "name_ru": name_ru,
            "segment": s.segment_key or "default",
            "segment_label": getattr(s, "segment_label", s.segment_key or "default"),
            "lot": {
                "buy_unit": round(s.buy_unit_price, 2),
            },
            "fair": {
                "median_3d": round(s.fair_price, 2),
                "p25_3d": round(s.floor_sell_unit, 2),
                "p75_3d": round(s.target_sell_unit, 2),
            },
            "liquidity": {
                "units_per_day": round(s.liquidity_units_per_day, 1),
                "days_to_sell_est": round(s.expected_days_to_sell, 1),
            },
            "plan": {
                "buy_max_unit": round(s.buy_max_unit, 2),
                "sell_target_unit": round(s.target_sell_unit, 2),
                "sell_floor_unit": round(s.floor_sell_unit, 2),
                "list_when": s.list_when,
                "expected_profit": round(s.expected_profit, 0),
                "roi": round(s.roi, 3),
            },
            "confidence": round(s.confidence, 2),
            "reasons": s.reasons,
            "caveats": s.caveats,
        }
        top_opportunities.append(opportunity)

    digest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_freshness_minutes": round(data_freshness_minutes, 1),
        "region": region,
        "config": {
            "auction_fee_rate": econ.get("auction_fee_rate", 0.05),
            "listing_fee": econ.get("listing_fee", 0),
            "capital": econ.get("total_capital", 10_000_000),
            "min_roi": strat.get("min_roi", 0.12),
        },
        "market_summary": {
            "tracked_items": tracked_items_count,
            "turnover_24h": round(turnover_24h, 0),
            "signals_found": len(sorted_signals),
            "notes": [
                "Цены указаны за штуку. Задержка данных ~10-15 минут.",
                "Перед выкупом лота проверьте наличие в игре через поиск по аукциону.",
            ],
        },
        "top_opportunities": top_opportunities,
        "avoid": avoid_list,
        "positions": positions or [],
    }
    return digest


def export_digest_json(digest: Dict[str, Any], file_path: str):
    """Write digest to disk as formatted JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
