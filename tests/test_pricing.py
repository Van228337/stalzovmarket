from datetime import datetime, timezone, timedelta
import pytest
from analytics.pricing import (
    SaleRecord,
    calculate_trimmed_window,
    compute_fair_price_metrics,
)


def test_calculate_trimmed_window():
    now = datetime.now(timezone.utc)
    # 10 sales with clear outliers at 10 and 1000
    sales = [
        SaleRecord(amount=1, price=10, sold_at=now),    # low outlier
        SaleRecord(amount=1, price=100, sold_at=now),
        SaleRecord(amount=1, price=105, sold_at=now),
        SaleRecord(amount=1, price=110, sold_at=now),
        SaleRecord(amount=1, price=112, sold_at=now),
        SaleRecord(amount=1, price=115, sold_at=now),
        SaleRecord(amount=1, price=118, sold_at=now),
        SaleRecord(amount=1, price=120, sold_at=now),
        SaleRecord(amount=1, price=125, sold_at=now),
        SaleRecord(amount=1, price=1000, sold_at=now),  # high outlier
    ]

    trimmed = calculate_trimmed_window(sales, trim_ratio=0.10)
    trimmed_prices = [s.price for s in trimmed]

    assert 10 not in trimmed_prices
    assert 1000 not in trimmed_prices
    assert len(trimmed) == 8


def test_fair_price_metrics_and_volatility():
    now = datetime.now(timezone.utc)
    # Generate stable sales around 500
    sales = [
        SaleRecord(amount=1, price=p, sold_at=now - timedelta(hours=i * 2))
        for i, p in enumerate([480, 490, 500, 510, 520, 500, 495, 505, 500, 515,
                               485, 495, 500, 505, 510, 500, 490, 510, 500, 505])
    ]

    metrics = compute_fair_price_metrics(sales, now=now, half_life_days=3.0)
    assert metrics is not None
    assert 495 <= metrics.median <= 505
    assert metrics.p25 < metrics.median < metrics.p75
    assert metrics.mad_volatility < 0.10
    assert metrics.trend == "flat"
    assert not metrics.is_spike


def test_spike_detection():
    now = datetime.now(timezone.utc)
    # 20 historical sales around 200, but last 2 sales at 400 (spike)
    sales = [
        SaleRecord(amount=1, price=200, sold_at=now - timedelta(days=2))
        for _ in range(18)
    ]
    # Add 2 sudden high sales in the last 2 hours
    sales.append(SaleRecord(amount=1, price=450, sold_at=now - timedelta(hours=1)))
    sales.append(SaleRecord(amount=1, price=460, sold_at=now - timedelta(hours=2)))

    metrics = compute_fair_price_metrics(sales, now=now, half_life_days=3.0)
    assert metrics is not None
    assert metrics.is_spike is True
    assert metrics.trend == "spike"
