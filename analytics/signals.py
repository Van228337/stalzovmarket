"""Signal generation and deal ranking engine (Section 7.6).

Computes:
- buy_unit = buyout_price / amount
- sell_target = P50 (with trend adjustment)
- sell_floor = P25
- net_sell(x) = x * (1 - AUCTION_FEE_RATE) - LISTING_FEE
- profit_expected = (net_sell(sell_target) - buy_unit) * amount
- profit_floor = (net_sell(sell_floor) - buy_unit) * amount
- roi = profit_expected / (buy_unit * amount)
- expected_days_to_sell = supply_below_target / units_per_day
- confidence [0..1] and risk-adjusted ranking score
- reasons[] and caveats[]
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from analytics.pricing import FairPriceMetrics


@dataclass
class ActiveLot:
    id: Optional[int]
    item_id: str
    region: str
    amount: int
    start_price: int
    current_price: int
    buyout_price: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    additional: Optional[Dict[str, Any]] = None
    qlt: Optional[int] = None
    segment_key: str = ""
    segment_label: str = ""
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    @property
    def unit_buyout(self) -> float:
        return float(self.buyout_price) / max(1, self.amount)


@dataclass
class TradeSignal:
    item_id: str
    region: str
    lot_id: Optional[int]
    segment_key: str
    buy_unit_price: float
    buy_max_unit: float
    fair_price: float
    target_sell_unit: float
    floor_sell_unit: float
    expected_profit: float
    profit_floor: float
    roi: float
    expected_days_to_sell: float
    liquidity_units_per_day: float
    confidence: float
    score: float
    data_age_min: float
    list_when: str
    segment_label: str = ""
    reasons: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)


def calculate_signal(
    lot: ActiveLot,
    metrics: FairPriceMetrics,
    active_lots_in_segment: List[ActiveLot],
    config: Dict[str, Any],
    data_age_min: float = 10.0,
) -> Optional[TradeSignal]:
    """Evaluate whether an active lot qualifies as an actionable arbitrage / flip signal."""
    # Disregard lots without buyout price
    if lot.buyout_price <= 0 or lot.amount <= 0:
        return None

    econ = config.get("economics", {})
    strat = config.get("strategy", {})

    fee_rate = float(econ.get("auction_fee_rate", 0.05))
    listing_fee = float(econ.get("listing_fee", 0))
    total_capital = float(econ.get("total_capital", 10_000_000))
    max_capital_share = float(econ.get("max_capital_share_per_deal", 0.25))

    min_roi = float(strat.get("min_roi", 0.12))
    min_profit_abs = float(strat.get("min_profit_abs", 30000))
    min_confidence = float(strat.get("min_confidence", 0.60))
    max_hold_days = float(strat.get("max_hold_days", 3.0))

    buy_unit = lot.unit_buyout
    lot_total_cost = lot.buyout_price

    # Guard: Deal exceeds max capital share
    if lot_total_cost > (total_capital * max_capital_share):
        return None

    # Target sell price: median (with modest trend adjustment)
    target_sell_unit = metrics.median
    if metrics.trend == "growth":
        target_sell_unit = min(metrics.p75, metrics.median * min(1.10, metrics.trend_ratio))
    elif metrics.trend == "falling":
        target_sell_unit = max(metrics.p25, metrics.median * max(0.90, metrics.trend_ratio))

    floor_sell_unit = metrics.p25

    def net_sell(price_per_unit: float) -> float:
        return price_per_unit * (1.0 - fee_rate) - listing_fee

    net_target = net_sell(target_sell_unit)
    net_floor = net_sell(floor_sell_unit)

    profit_expected = (net_target - buy_unit) * lot.amount
    profit_floor = (net_floor - buy_unit) * lot.amount

    if lot_total_cost <= 0:
        return None
    roi = profit_expected / lot_total_cost

    # Max unit purchase price where deal still meets min_roi and min_profit_abs
    max_price_for_roi = net_target / (1.0 + min_roi)
    max_price_for_profit = net_target - (min_profit_abs / lot.amount)
    buy_max_unit = max(0.0, min(max_price_for_roi, max_price_for_profit))

    # Calculate supply pressure and expected days to sell
    cheaper_supply_units = sum(
        l.amount
        for l in active_lots_in_segment
        if l.buyout_price > 0 and l.unit_buyout <= target_sell_unit and (l.id != lot.id)
    )
    units_per_day = max(0.1, metrics.units_per_day)
    expected_days_to_sell = cheaper_supply_units / units_per_day

    # Confidence calculation:
    # Base: 0.90 - penalties
    base_conf = 0.90
    conf = base_conf - metrics.confidence_penalty

    # Age penalty (~10-20 min latency on EXBO API)
    if data_age_min > 20:
        conf -= min(0.20, (data_age_min - 20) * 0.01)

    # Days to sell penalty
    if expected_days_to_sell > max_hold_days:
        conf -= 0.15

    confidence = max(0.10, min(0.98, conf))

    # Score: Risk-adjusted expected profit per day
    # Score = expected_profit * confidence * (1.0 + roi) / max(0.5, expected_days_to_sell)
    turnover_rate = 1.0 / max(0.5, expected_days_to_sell)
    score = profit_expected * confidence * turnover_rate

    # Build human-readable explanations (Section 7.6)
    reasons = [
        f"Цена покупки за шт.: {buy_unit:,.0f} против медианы 3д: {metrics.median:,.0f} (выборка: {metrics.sample_size} сделок)",
        f"Ликвидность: {metrics.units_per_day:.1f} шт/сут ({metrics.sales_per_day:.1f} сделок/сут)",
        f"Активное предложение ниже/равно цели ({target_sell_unit:,.0f}): {cheaper_supply_units} шт (оценка срока: {expected_days_to_sell:.1f} дн.)",
        f"Тренд: {metrics.trend} (соотношение 24ч/7д: {metrics.trend_ratio:.2f}), волатильность MAD: {metrics.mad_volatility*100:.1f}%",
        f"Ожидаемый профит: +{profit_expected:,.0f} (ROI {roi*100:.1f}%), худший сценарий (P25): +{profit_floor:,.0f}",
    ]

    caveats = []
    caveats.append(f"Задержка API ~10-15 мин (возраст снимка {data_age_min:.0f} мин) — лот может быть выкуплен другим игроком.")
    if metrics.is_thin_market:
        caveats.append(f"Тонкий рынок: малый размер выборки ({metrics.sample_size} < 20 сделок).")
    if metrics.is_spike:
        caveats.append("Зафиксирован ценовой всплеск/манипуляция: недавние цены аномально выше медианы без роста объёма.")
    if expected_days_to_sell > 2.0:
        caveats.append(f"Высокое давление конкурентов: перед вами {cheaper_supply_units} шт. дешевле целевой цены.")
    if metrics.mad_volatility > 0.20:
        caveats.append(f"Повышенная волатильность ({metrics.mad_volatility*100:.1f}%): возможна коррекция цены.")

    # Determine recommended listing time/schedule
    list_when = "Выставлять сразу" if metrics.trend in ("growth", "flat") else "Выставлять порциями в часы пикового онлайна (вечер МСК)"

    # Strict qualification conditions
    passes_filter = (
        profit_floor >= 0  # Pessimistic scenario does not lose capital
        and profit_expected >= min_profit_abs
        and roi >= min_roi
        and expected_days_to_sell <= max_hold_days
        and confidence >= min_confidence
        and not metrics.is_spike
    )

    if not passes_filter:
        return None

    return TradeSignal(
        item_id=lot.item_id,
        region=lot.region,
        lot_id=lot.id,
        segment_key=lot.segment_key,
        segment_label=lot.segment_label or lot.segment_key or "default",
        buy_unit_price=buy_unit,
        buy_max_unit=buy_max_unit,
        fair_price=metrics.median,
        target_sell_unit=target_sell_unit,
        floor_sell_unit=floor_sell_unit,
        expected_profit=profit_expected,
        profit_floor=profit_floor,
        roi=roi,
        expected_days_to_sell=expected_days_to_sell,
        liquidity_units_per_day=metrics.units_per_day,
        confidence=confidence,
        score=score,
        data_age_min=data_age_min,
        list_when=list_when,
        reasons=reasons,
        caveats=caveats,
    )
