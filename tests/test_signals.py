from datetime import datetime, timezone
import pytest
from analytics.pricing import FairPriceMetrics
from analytics.signals import ActiveLot, calculate_signal


@pytest.fixture
def base_config():
    return {
        "economics": {
            "auction_fee_rate": 0.05,
            "listing_fee": 0,
            "total_capital": 10_000_000,
            "max_capital_share_per_deal": 0.25,
        },
        "strategy": {
            "min_roi": 0.10,
            "min_profit_abs": 20_000,
            "min_confidence": 0.50,
            "max_hold_days": 3.0,
        },
    }


@pytest.fixture
def base_metrics():
    return FairPriceMetrics(
        sample_size=40,
        raw_sample_size=45,
        median=500_000,
        p25=460_000,
        p75=540_000,
        iqr=80_000,
        mad_volatility=0.08,
        trend="flat",
        trend_ratio=1.0,
        units_per_day=20.0,
        sales_per_day=15.0,
        is_spike=False,
        is_thin_market=False,
        confidence_penalty=0.0,
    )


def test_profitable_signal_generation(base_config, base_metrics):
    # Lot buyout: 350,000 for 1 unit.
    # Fair median: 500,000. Floor P25: 460,000.
    # Net sell at 500k (-5% fee) = 475,000.
    # Net profit expected = 475,000 - 350,000 = 125,000.
    # Net sell at 460k (-5% fee) = 437,000.
    # Profit floor = 437,000 - 350,000 = 87,000 >= 0.
    # ROI = 125,000 / 350,000 = 35.7% > 10%.
    lot = ActiveLot(
        id=1,
        item_id="y1q9",
        region="RU",
        amount=1,
        start_price=100_000,
        current_price=100_000,
        buyout_price=350_000,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )

    signal = calculate_signal(
        lot=lot,
        metrics=base_metrics,
        active_lots_in_segment=[],
        config=base_config,
        data_age_min=10.0,
    )

    assert signal is not None
    assert signal.buy_unit_price == 350_000
    assert signal.expected_profit == 125_000
    assert signal.profit_floor == 87_000
    assert round(signal.roi, 3) == 0.357
    assert signal.confidence > 0.70
    assert len(signal.reasons) > 0
    assert len(signal.caveats) > 0


def test_reject_when_floor_profit_negative(base_config, base_metrics):
    # Lot buyout is 450,000.
    # Floor is 460,000. Net floor at 460k (-5%) = 437,000.
    # 437,000 - 450,000 = -13,000 < 0! Must be rejected.
    lot = ActiveLot(
        id=2,
        item_id="y1q9",
        region="RU",
        amount=1,
        start_price=200_000,
        current_price=200_000,
        buyout_price=450_000,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
    )

    signal = calculate_signal(
        lot=lot,
        metrics=base_metrics,
        active_lots_in_segment=[],
        config=base_config,
        data_age_min=10.0,
    )

    assert signal is None
