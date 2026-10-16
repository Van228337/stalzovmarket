"""Historical Backtesting and Confidence Calibration Engine (Section 7.7).

Replays trade signals against historical completed sales to measure:
- Win rate (% profitable trades after auction fee)
- Realized profit and ROI distributions
- Average liquidation duration (hours/days to sale)
- Confidence calibration (e.g. 80% confidence bucket vs actual win rate)
- Maximum drawdown
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from analytics.pricing import SaleRecord, compute_fair_price_metrics
from analytics.signals import ActiveLot, calculate_signal, TradeSignal


@dataclass
class BacktestTrade:
    item_id: str
    signal_time: datetime
    buy_price: float
    target_sell_price: float
    floor_sell_price: float
    realized_sell_price: Optional[float]
    realized_profit: Optional[float]
    realized_roi: Optional[float]
    hours_to_sell: Optional[float]
    is_win: bool
    confidence_bucket: str  # e.g. "0.6-0.7", "0.7-0.8", "0.8-0.9"


@dataclass
class BacktestSummary:
    total_signals: int
    executed_trades: int
    profitable_trades: int
    win_rate: float
    average_roi: float
    median_roi: float
    average_hours_to_sell: float
    max_drawdown_pct: float
    calibration: Dict[str, Dict[str, float]]
    verdict: str


def run_historical_backtest(
    sales: List[SaleRecord],
    simulated_lots: List[ActiveLot],
    config: Dict[str, Any],
    fee_rate: float = 0.05,
    max_hold_hours: float = 72.0,
) -> BacktestSummary:
    """Simulate trading strategy over historical sales timeline."""
    trades: List[BacktestTrade] = []
    sorted_sales = sorted(sales, key=lambda s: s.sold_at)

    for lot in simulated_lots:
        lot_time = lot.start_time or datetime.now(timezone.utc)
        # Sales known strictly before lot_time (no lookahead bias)
        prior_sales = [s for s in sorted_sales if s.sold_at < lot_time]
        if len(prior_sales) < 15:
            continue

        metrics = compute_fair_price_metrics(prior_sales, now=lot_time)
        if not metrics or metrics.is_spike:
            continue

        signal = calculate_signal(lot, metrics, [], config)
        if not signal:
            continue

        # Look for subsequent sales matching this item after lot_time up to max_hold_hours
        subsequent_sales = [
            s for s in sorted_sales
            if lot_time <= s.sold_at <= (lot_time + timedelta(hours=max_hold_hours))
        ]

        conf_bucket = f"{int(signal.confidence * 10) / 10:.1f}-{int(signal.confidence * 10) / 10 + 0.1:.1f}"

        if not subsequent_sales:
            # Expired without sale within hold window (liquidation at floor or stop loss)
            loss = (signal.floor_sell_unit * (1 - fee_rate) - signal.buy_unit_price) * lot.amount
            trades.append(BacktestTrade(
                item_id=lot.item_id,
                signal_time=lot_time,
                buy_price=signal.buy_unit_price,
                target_sell_price=signal.target_sell_unit,
                floor_sell_price=signal.floor_sell_unit,
                realized_sell_price=signal.floor_sell_unit,
                realized_profit=loss,
                realized_roi=loss / (signal.buy_unit_price * lot.amount),
                hours_to_sell=max_hold_hours,
                is_win=loss > 0,
                confidence_bucket=conf_bucket,
            ))
            continue

        # Find best matching subsequent sale
        matched_sale = None
        for s in subsequent_sales:
            if s.unit_price >= signal.floor_sell_unit:
                matched_sale = s
                break
        if not matched_sale:
            matched_sale = subsequent_sales[0]

        hours_to_sell = (matched_sale.sold_at - lot_time).total_seconds() / 3600.0
        realized_price = min(signal.target_sell_unit, matched_sale.unit_price)
        net_proceeds = realized_price * (1.0 - fee_rate)
        profit = (net_proceeds - signal.buy_unit_price) * lot.amount
        roi = profit / (signal.buy_unit_price * lot.amount)

        trades.append(BacktestTrade(
            item_id=lot.item_id,
            signal_time=lot_time,
            buy_price=signal.buy_unit_price,
            target_sell_price=signal.target_sell_unit,
            floor_sell_price=signal.floor_sell_unit,
            realized_sell_price=realized_price,
            realized_profit=profit,
            realized_roi=roi,
            hours_to_sell=hours_to_sell,
            is_win=profit > 0,
            confidence_bucket=conf_bucket,
        ))

    total = len(trades)
    if total == 0:
        return BacktestSummary(
            total_signals=0,
            executed_trades=0,
            profitable_trades=0,
            win_rate=0.0,
            average_roi=0.0,
            median_roi=0.0,
            average_hours_to_sell=0.0,
            max_drawdown_pct=0.0,
            calibration={},
            verdict="Insufficient data for backtest evaluation.",
        )

    wins = sum(1 for t in trades if t.is_win)
    rois = [t.realized_roi for t in trades if t.realized_roi is not None]
    hours = [t.hours_to_sell for t in trades if t.hours_to_sell is not None]

    win_rate = wins / total
    avg_roi = float(np.mean(rois)) if rois else 0.0
    med_roi = float(np.median(rois)) if rois else 0.0
    avg_hours = float(np.mean(hours)) if hours else 0.0

    # Calibration table by confidence bucket
    calibration: Dict[str, Dict[str, float]] = {}
    buckets = set(t.confidence_bucket for t in trades)
    for b in sorted(buckets):
        b_trades = [t for t in trades if t.confidence_bucket == b]
        b_wins = sum(1 for t in b_trades if t.is_win)
        calibration[b] = {
            "trades": len(b_trades),
            "actual_win_rate": round(b_wins / len(b_trades), 2),
        }

    # Drawdown calculation
    cumulative = np.cumsum([t.realized_profit or 0.0 for t in trades])
    peak = np.maximum.accumulate(cumulative)
    drawdowns = peak - cumulative
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    verdict = (
        f"Passed: Win rate {win_rate*100:.1f}%, Median ROI {med_roi*100:.1f}%, Avg holding {avg_hours:.1f}h."
        if win_rate >= 0.70 and med_roi >= 0.10
        else f"Warning: Win rate {win_rate*100:.1f}% or Median ROI {med_roi*100:.1f}% below target thresholds."
    )

    return BacktestSummary(
        total_signals=total,
        executed_trades=total,
        profitable_trades=wins,
        win_rate=round(win_rate, 3),
        average_roi=round(avg_roi, 3),
        median_roi=round(med_roi, 3),
        average_hours_to_sell=round(avg_hours, 1),
        max_drawdown_pct=round(max_dd, 2),
        calibration=calibration,
        verdict=verdict,
    )
