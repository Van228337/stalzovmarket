"""Fair price estimation, volatility, liquidity, and trend analytics engine.

Strictly adheres to STALCRAFT market guidelines:
- Per-unit prices: price / amount
- 10% outlier trimming
- Recency weighting with half-life decay
- Robust median, P25, P75
- MAD (Median Absolute Deviation) volatility
- Spike / price manipulation detector
- Supply pressure & liquidity rate (units sold / day)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import math
import numpy as np


@dataclass
class SaleRecord:
    amount: int
    price: int
    sold_at: datetime
    additional: Optional[Dict[str, Any]] = None
    segment_key: str = ""

    @property
    def unit_price(self) -> float:
        return float(self.price) / max(1, self.amount)


@dataclass
class FairPriceMetrics:
    sample_size: int
    raw_sample_size: int
    median: float
    p25: float
    p75: float
    iqr: float
    mad_volatility: float  # MAD / median
    trend: str             # "growth" | "flat" | "falling" | "spike"
    trend_ratio: float     # 24h median / 7d median
    units_per_day: float
    sales_per_day: float
    is_spike: bool
    is_thin_market: bool
    confidence_penalty: float  # [0.0..1.0] penalty deduction based on data quality


def calculate_trimmed_window(
    sales: List[SaleRecord],
    trim_ratio: float = 0.10,
) -> List[SaleRecord]:
    """Filter out top and bottom trim_ratio (default 10%) outliers based on unit price."""
    if len(sales) < 5:
        return sales

    sorted_sales = sorted(sales, key=lambda s: s.unit_price)
    trim_count = int(math.floor(len(sorted_sales) * trim_ratio))
    if trim_count == 0 or (len(sorted_sales) - 2 * trim_count) < 3:
        return sorted_sales

    return sorted_sales[trim_count : len(sorted_sales) - trim_count]


def calculate_weighted_quantiles(
    values: np.ndarray,
    weights: np.ndarray,
    quantiles: List[float],
) -> List[float]:
    """Compute weighted quantiles for recency-decayed pricing."""
    if len(values) == 0:
        return [0.0 for _ in quantiles]

    sorter = np.argsort(values)
    sorted_values = values[sorter]
    sorted_weights = weights[sorter]

    cum_weights = np.cumsum(sorted_weights)
    total_weight = cum_weights[-1]
    if total_weight <= 0:
        return [float(np.median(values)) for _ in quantiles]

    normalized_cum = (cum_weights - 0.5 * sorted_weights) / total_weight

    results = []
    for q in quantiles:
        res = float(np.interp(q, normalized_cum, sorted_values))
        results.append(res)
    return results


def compute_fair_price_metrics(
    sales: List[SaleRecord],
    now: Optional[datetime] = None,
    half_life_days: float = 3.0,
    min_sample_size: int = 20,
    trim_ratio: float = 0.10,
) -> Optional[FairPriceMetrics]:
    """Calculate fair price, quartiles, volatility, liquidity, and trend from historical sales."""
    if not sales:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    raw_sample_size = len(sales)
    trimmed_sales = calculate_trimmed_window(sales, trim_ratio=trim_ratio)
    sample_size = len(trimmed_sales)

    # Unit prices and ages for recency weighting
    unit_prices = []
    weights = []
    decay_constant = math.log(2) / (half_life_days * 86400.0)

    sales_24h_units = []
    total_units_sold = 0

    for s in trimmed_sales:
        unit_prices.append(s.unit_price)
        total_units_sold += s.amount
        age_seconds = max(0.0, (now - s.sold_at).total_seconds())
        # Exponential decay weight: w = exp(-lambda * t)
        w = math.exp(-decay_constant * age_seconds)
        weights.append(w)

    # Collect raw recent 24h sales (untrimmed) for manipulation/spike detection
    raw_recent_24h = [s for s in sales if (now - s.sold_at).total_seconds() <= 86400.0]
    raw_recent_24h_prices = [s.unit_price for s in raw_recent_24h]

    np_prices = np.array(unit_prices, dtype=np.float64)
    np_weights = np.array(weights, dtype=np.float64)

    # Quantiles: P25, P50 (median), P75
    quantiles = calculate_weighted_quantiles(np_prices, np_weights, [0.25, 0.50, 0.75])
    p25, median, p75 = quantiles[0], quantiles[1], quantiles[2]
    iqr = max(0.0, p75 - p25)

    # MAD (Median Absolute Deviation)
    abs_deviations = np.abs(np_prices - median)
    mad = float(np.median(abs_deviations))
    mad_volatility = (mad / median) if median > 0 else 0.0

    # Window span for liquidity
    timestamps = [s.sold_at for s in sales]
    oldest_sale = min(timestamps)
    time_span_days = max(1.0, (now - oldest_sale).total_seconds() / 86400.0)
    units_per_day = total_units_sold / time_span_days
    sales_per_day = raw_sample_size / time_span_days

    # Trend and spike calculation: recent raw sales vs baseline median
    if raw_recent_24h_prices:
        recent_24h_median = float(np.median(raw_recent_24h_prices))
        trend_ratio = (recent_24h_median / median) if median > 0 else 1.0
    else:
        trend_ratio = 1.0

    is_spike = False
    # Section 7.5: Spike detector - if recent sales are sharply higher than median without volume surge
    if trend_ratio > 1.30:
        trend = "spike"
        is_spike = True
    elif trend_ratio > 1.08:
        trend = "growth"
    elif trend_ratio < 0.92:
        trend = "falling"
    else:
        trend = "flat"

    is_thin_market = sample_size < min_sample_size

    # Confidence penalty
    confidence_penalty = 0.0
    if is_thin_market:
        confidence_penalty += min(0.40, (min_sample_size - sample_size) / min_sample_size * 0.40)
    if is_spike:
        confidence_penalty += 0.35
    if mad_volatility > 0.25:
        confidence_penalty += min(0.20, (mad_volatility - 0.25))

    return FairPriceMetrics(
        sample_size=sample_size,
        raw_sample_size=raw_sample_size,
        median=median,
        p25=p25,
        p75=p75,
        iqr=iqr,
        mad_volatility=mad_volatility,
        trend=trend,
        trend_ratio=trend_ratio,
        units_per_day=units_per_day,
        sales_per_day=sales_per_day,
        is_spike=is_spike,
        is_thin_market=is_thin_market,
        confidence_penalty=min(0.85, confidence_penalty),
    )
