from datetime import datetime, timezone, timedelta
import pytest
from analytics.pricing import SaleRecord
from analytics.signals import ActiveLot
from analytics.backtest import run_historical_backtest


def test_historical_backtest_execution():
    base_time = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    # 30 historical baseline sales at ~100k
    sales = [
        SaleRecord(
            amount=1,
            price=100_000,
            sold_at=base_time + timedelta(hours=i * 2),
        )
        for i in range(30)
    ]

    # Add future sales after day 3 (hours 72+) at ~100k
    sales.extend([
        SaleRecord(
            amount=1,
            price=100_000,
            sold_at=base_time + timedelta(hours=65 + i * 2),
        )
        for i in range(15)
    ])

    # Simulated lot appearing at hour 62: price is 70k (profitable flip)
    lot = ActiveLot(
        id=101,
        item_id="y1q9",
        region="RU",
        amount=1,
        start_price=50_000,
        current_price=50_000,
        buyout_price=70_000,
        start_time=base_time + timedelta(hours=62),
        end_time=base_time + timedelta(hours=86),
    )

    config = {
        "economics": {
            "auction_fee_rate": 0.05,
            "listing_fee": 0,
            "total_capital": 10_000_000,
            "max_capital_share_per_deal": 0.25,
        },
        "strategy": {
            "min_roi": 0.10,
            "min_profit_abs": 10_000,
            "min_confidence": 0.50,
            "max_hold_days": 3.0,
        },
    }

    summary = run_historical_backtest(
        sales=sales,
        simulated_lots=[lot],
        config=config,
        fee_rate=0.05,
    )

    assert summary.total_signals == 1
    assert summary.profitable_trades == 1
    assert summary.win_rate == 1.0
    assert summary.average_roi > 0.20
    assert "Passed" in summary.verdict
