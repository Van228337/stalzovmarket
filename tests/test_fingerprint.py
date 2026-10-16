from datetime import datetime, timezone, timedelta
import pytest
from collector.fingerprint import (
    compute_lot_fingerprint,
    compute_sale_hash,
    match_disappeared_lot,
)
from collector.client import StalcraftClient


def test_compute_lot_fingerprint_deterministic():
    fp1 = compute_lot_fingerprint(
        item_id="1pyq",
        amount=1,
        start_price=0,
        buyout_price=300000,
        start_time="2026-10-16T10:00:00Z",
        end_time="2026-10-16T16:00:00Z",
        additional={"qlt": 1, "attributes": [{"type": 1, "definitionId": "recoil_suf"}]},
    )
    fp2 = compute_lot_fingerprint(
        item_id="1pyq",
        amount=1,
        start_price=0,
        buyout_price=300000,
        start_time="2026-10-16T10:00:00Z",
        end_time="2026-10-16T16:00:00Z",
        additional={"attributes": [{"definitionId": "recoil_suf", "type": 1}], "qlt": 1},
    )
    # Different key ordering in dict must produce identical hash
    assert fp1 == fp2


def test_match_disappeared_lot_probable_sold():
    now = datetime.now(timezone.utc)
    recent_sales = [
        {"amount": 5, "price": 50000, "sold_at": (now - timedelta(minutes=5)).isoformat()},
        {"amount": 1, "price": 298000, "sold_at": (now - timedelta(minutes=10)).isoformat()},
    ]

    status, conf = match_disappeared_lot(
        lot_price=300000,
        lot_amount=1,
        lot_last_seen=now - timedelta(minutes=12),
        recent_sales=recent_sales,
        price_tolerance_pct=0.02, # 2% tolerance = 6000
    )

    assert status == "probable_sold"
    assert conf is not None and conf > 0.70


def test_stale_slice_detector():
    client = StalcraftClient()
    # When sort=buyout_price and order=asc, lots must be non-decreasing
    valid_lots = [
        {"buyout_price": 100},
        {"buyout_price": 200},
        {"buyout_price": 300},
    ]
    assert client.check_stale_slice(valid_lots, sort_key="buyout_price", order="asc") is False

    # Cloudflare stale slice anomaly: returns lots in arbitrary or descending order
    stale_lots = [
        {"buyout_price": 500},
        {"buyout_price": 200},
        {"buyout_price": 300},
    ]
    assert client.check_stale_slice(stale_lots, sort_key="buyout_price", order="asc") is True
