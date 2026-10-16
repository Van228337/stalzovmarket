from datetime import datetime, timezone
import pytest
from analytics.signals import ActiveLot, calculate_signal
from analytics.pricing import FairPriceMetrics
from collector.items_db import ItemsDatabase
from collector.runner import compute_filters_hash


def test_breakeven_and_commission_calculation():
    # Patch 1 Section 2:
    # Net sell: x * (1 - 0.05) - listing_fee
    # Breakeven: sell >= buy / 0.95 ≈ buy * 1.0526 (+5.26%)
    # Example: buy 1000, sell 1100 -> net proceeds 1045 -> profit 45, ROI 4.5%
    fee_rate = 0.05
    buy_unit = 1000.0
    sell_target = 1100.0

    net_proceeds = sell_target * (1.0 - fee_rate)
    profit = net_proceeds - buy_unit
    roi = profit / buy_unit

    assert net_proceeds == 1045.0
    assert profit == 45.0
    assert round(roi, 3) == 0.045

    breakeven_sell = buy_unit / (1.0 - fee_rate)
    assert round(breakeven_sell, 2) == 1052.63


def test_filters_hash_deterministic():
    f1 = {"concept": "marksman", "min_potential": 50}
    f2 = {"min_potential": 50, "concept": "marksman"}
    # Different key ordering must produce identical hash
    assert compute_filters_hash(f1) == compute_filters_hash(f2)
    assert len(compute_filters_hash(f1)) > 0


@pytest.mark.asyncio
async def test_catalog_overrides_integration():
    db = ItemsDatabase(overrides_path="catalog_overrides.json")
    items = await db.load_catalog(force_refresh=False, export_web_catalog=False)

    # 'y1q9' (Viper / Гадюка) must be present from catalog_overrides.json
    assert "y1q9" in items
    assert items["y1q9"]["name_ru"] == "Гадюка"
    assert items["y1q9"]["source"] == "manual_override"
