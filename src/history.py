"""Historical time series -- the backbone for real charts and real anomaly detection.

Without history, "anomaly detection" degenerates into hardcoded thresholds that
someone picked by feel. With 90 days of price and years of TVL, a deviation can
be measured against what the metric actually does, not against a guess.

All series come from the same free, key-less endpoints already in use.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .http_client import FetchError, safe_get

PRICE_HISTORY_URL = "https://api.coingecko.com/api/v3/coins/solana/market_chart?vs_currency=usd&days={days}&interval=daily"
TVL_HISTORY_URL = "https://api.llama.fi/v2/historicalChainTvl/Solana"
DEX_HISTORY_URL = "https://api.llama.fi/overview/dexs/solana"


@dataclass
class Series:
    """A named time series: parallel lists of unix-seconds and values."""
    name: str
    timestamps: list[int] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    unit: str = ""

    def __len__(self) -> int:
        return len(self.values)

    @property
    def latest(self) -> float | None:
        return self.values[-1] if self.values else None

    def pct_change(self, periods: int = 1) -> float | None:
        """Percent change over the last `periods` steps."""
        if len(self.values) <= periods:
            return None
        prev = self.values[-1 - periods]
        if prev == 0:
            return None
        return round(100 * (self.values[-1] - prev) / prev, 2)

    def zscore(self, window: int = 30) -> float | None:
        """How many standard deviations the latest value sits from the recent mean.

        Uses the window *excluding* the latest point, so the current value is
        measured against its own history rather than against a mean it helped
        create.
        """
        if len(self.values) < window + 1:
            return None
        baseline = self.values[-window - 1:-1]
        mean = statistics.fmean(baseline)
        try:
            sd = statistics.stdev(baseline)
        except statistics.StatisticsError:
            return None
        if sd == 0:
            return None
        return round((self.values[-1] - mean) / sd, 2)

    def daily_returns(self) -> list[float]:
        out = []
        for prev, cur in zip(self.values, self.values[1:]):
            if prev:
                out.append((cur - prev) / prev)
        return out


@dataclass
class HistoryBundle:
    price: Series = field(default_factory=lambda: Series("SOL price", unit="USD"))
    tvl: Series = field(default_factory=lambda: Series("Solana TVL", unit="USD"))
    dex_volume: Series = field(default_factory=lambda: Series("DEX volume", unit="USD"))
    errors: list[str] = field(default_factory=list)


def fetch_history(days: int = 90, tvl_days: int = 180) -> HistoryBundle:
    h = HistoryBundle()

    try:
        d = safe_get(PRICE_HISTORY_URL.format(days=days), "coingecko_history")
        for ts_ms, value in d.get("prices", []):
            h.price.timestamps.append(int(ts_ms / 1000))
            h.price.values.append(round(float(value), 4))
    except (FetchError, KeyError, TypeError, ValueError) as e:
        h.errors.append(f"price_history: {e}")

    try:
        series = safe_get(TVL_HISTORY_URL, "defillama_tvl_history")
        for point in series[-tvl_days:]:
            h.tvl.timestamps.append(int(point["date"]))
            h.tvl.values.append(round(float(point["tvl"]), 2))
    except (FetchError, KeyError, TypeError, ValueError) as e:
        h.errors.append(f"tvl_history: {e}")

    try:
        d = safe_get(DEX_HISTORY_URL, "defillama_dex_history")
        for ts, value in (d.get("totalDataChart") or [])[-tvl_days:]:
            h.dex_volume.timestamps.append(int(ts))
            h.dex_volume.values.append(round(float(value), 2))
    except (FetchError, KeyError, TypeError, ValueError) as e:
        h.errors.append(f"dex_history: {e}")

    return h
