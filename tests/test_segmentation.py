import pytest
from datetime import datetime, timezone
from analytics.segmentation import get_item_segment
from analytics.pricing import SaleRecord, compute_fair_price_metrics
from analytics.signals import ActiveLot, calculate_signal

def test_artefact_segmentation_keys_and_labels():
    meta = {"category": "artefact/electrophysical"}

    # Common +0
    key1, label1 = get_item_segment("wg53", meta, {"qlt": 0, "ptn": 0, "upgrade_bonus": 0.0})
    assert key1 == "q0:p0"
    assert label1 == "Обычный (+0)"

    # Special +10
    key2, label2 = get_item_segment("wg53", meta, {"qlt": 2, "ptn": 10, "upgrade_bonus": 0.15})
    assert key2 == "q2:p10"
    assert label2 == "Особый (+10)"

    # Rare +15
    key3, label3 = get_item_segment("gyq5", meta, {"qlt": 3, "ptn": 15, "upgrade_bonus": 0.30})
    assert key3 == "q3:p15"
    assert label3 == "Редкий (+15)"


def test_standard_item_segmentation():
    meta = {"category": "other"}
    key, label = get_item_segment("y3nmw", meta, None)
    assert key == "default"
    assert label == "Стандарт"


def test_segmented_sales_prevent_false_arbitrage_signals():
    # Simulate Atom (wg53) scenario:
    # 1. Active lot: Common +0 listed at 240,000
    lot_q0 = ActiveLot(
        id=1,
        item_id="wg53",
        region="RU",
        amount=1,
        start_price=240000,
        current_price=240000,
        buyout_price=240000,
        start_time=None,
        end_time=None,
        additional={"qlt": 0, "ptn": 0},
        qlt=0,
        segment_key="q0:p0",
        segment_label="Обычный (+0)"
    )

    # 2. Historical sales of Common +0 are around 250,000
    sales_q0 = [
        SaleRecord(amount=1, price=250000, sold_at=datetime.now(timezone.utc), segment_key="q0:p0")
        for _ in range(10)
    ]
    metrics_q0 = compute_fair_price_metrics(sales_q0, half_life_days=2.0)
    assert metrics_q0 is not None
    assert metrics_q0.median == 250000.0

    config = {
        "economics": {"auction_fee_rate": 0.05, "total_capital": 10000000, "max_capital_share_per_deal": 0.30},
        "strategy": {"min_roi": 0.10, "min_profit_abs": 50000, "min_confidence": 0.60}
    }

    # Signal against true segment (q0:p0):
    # Buy 240,000 -> Net sell 250,000 * 0.95 = 237,500 -> Profit = -2,500 (LOSS)
    # Must NOT produce a signal!
    signal = calculate_signal(lot_q0, metrics_q0, [lot_q0], config)
    assert signal is None, "Common +0 Atom at 240k must not generate a signal when fairly priced against 250k!"


def test_high_tier_artefact_arbitrage_detected():
    # If a Special +10 Atom (fair price ~4,000,000) is listed at 1,500,000
    lot_q2 = ActiveLot(
        id=2,
        item_id="wg53",
        region="RU",
        amount=1,
        start_price=1500000,
        current_price=1500000,
        buyout_price=1500000,
        start_time=None,
        end_time=None,
        additional={"qlt": 2, "ptn": 10},
        qlt=2,
        segment_key="q2:p10",
        segment_label="Особый (+10)"
    )

    sales_q2 = [
        SaleRecord(amount=1, price=4000000, sold_at=datetime.now(timezone.utc), segment_key="q2:p10")
        for _ in range(10)
    ]
    metrics_q2 = compute_fair_price_metrics(sales_q2, half_life_days=2.0)
    assert metrics_q2.median == 4000000.0

    config = {
        "economics": {"auction_fee_rate": 0.05, "total_capital": 10000000, "max_capital_share_per_deal": 0.30},
        "strategy": {"min_roi": 0.10, "min_profit_abs": 50000, "min_confidence": 0.60}
    }

    signal = calculate_signal(lot_q2, metrics_q2, [lot_q2], config)
    assert signal is not None
    assert signal.expected_profit == 2300000.0  # 4kk * 0.95 - 1.5kk = 2.3kk
    assert signal.segment_label == "Особый (+10)"
