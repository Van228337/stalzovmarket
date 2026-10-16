"""Lot fingerprinting, lifecycle tracking, and probabilistic trade matching (Section 7.3).

Generates deterministic hashes for lots and historical sales to support
idempotent upserts and lifecycle state transitions:
  - 'active': Currently visible in auction listings
  - 'probable_sold': Disappeared from full scan and matched by historical sale
  - 'expired_or_cancelled': Disappeared without a matching historical sale
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def normalize_json(obj: Any) -> str:
    """Deterministic JSON string for hashing (sorted keys, no spaces)."""
    if obj is None:
        return ""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_lot_fingerprint(
    item_id: str,
    amount: int,
    start_price: int,
    buyout_price: int,
    start_time: str,
    end_time: str,
    additional: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute unique SHA-256 fingerprint for an active lot.

    Hash combines item, volume, prices, duration timestamps, and normalized game attributes.
    """
    raw_str = (
        f"{item_id}|{amount}|{start_price}|{buyout_price}|"
        f"{start_time}|{end_time}|{normalize_json(additional)}"
    )
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def compute_sale_hash(
    item_id: str,
    sold_at: str,
    price: int,
    amount: int,
    additional: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute deduplication hash for a historical sale."""
    raw_str = f"{item_id}|{sold_at}|{price}|{amount}|{normalize_json(additional)}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def match_disappeared_lot(
    lot_price: int,
    lot_amount: int,
    lot_last_seen: datetime,
    recent_sales: List[Dict[str, Any]],
    price_tolerance_pct: float = 0.02,
    time_window_sec: float = 3600.0,
) -> Tuple[str, Optional[float]]:
    """Probabilistically match a lot that vanished from full auction scan to historical sales.

    Returns:
        (status, match_confidence)
        status: 'probable_sold' or 'expired_or_cancelled'
    """
    best_confidence = 0.0
    matched = False

    for sale in recent_sales:
        s_amount = sale.get("amount", 0)
        s_price = sale.get("price", 0)
        s_time = sale.get("sold_at")

        if isinstance(s_time, str):
            try:
                s_dt = datetime.fromisoformat(s_time.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(s_time, datetime):
            s_dt = s_time
        else:
            continue

        if s_amount != lot_amount:
            continue

        # Check price match (within tolerance or exact)
        price_diff = abs(s_price - lot_price)
        max_allowed_diff = max(100.0, lot_price * price_tolerance_pct)
        if price_diff > max_allowed_diff:
            continue

        # Check time window around last_seen
        time_diff = abs((s_dt - lot_last_seen).total_seconds())
        if time_diff <= time_window_sec:
            # Score confidence: higher when price is exact and time is close
            time_score = max(0.0, 1.0 - (time_diff / time_window_sec) * 0.5)
            price_score = max(0.0, 1.0 - (price_diff / max_allowed_diff) * 0.5)
            confidence = 0.5 + 0.3 * time_score + 0.2 * price_score
            if confidence > best_confidence:
                best_confidence = confidence
                matched = True

    if matched:
        return "probable_sold", round(best_confidence, 2)
    return "expired_or_cancelled", None
