"""Off-chain economic data: price, TVL, stablecoin supply, DEX volume.

CoinGecko and DeFiLlama both expose free tiers with no key required for the
endpoints used here. If a source rate-limits or times out, that section
degrades gracefully -- the report still runs with everything else intact,
because a stalled price feed should never be presented as a live number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .http_client import FetchError, safe_get

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/solana?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
DEFILLAMA_TVL_URL = "https://api.llama.fi/v2/historicalChainTvl/Solana"
DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoinchains"
DEFILLAMA_DEX_URL = "https://api.llama.fi/overview/dexs/solana"


@dataclass
class PriceInfo:
    usd: float | None = None
    market_cap_usd: float | None = None
    change_24h_pct: float | None = None
    volume_24h_usd: float | None = None
    ath_usd: float | None = None
    ath_change_pct: float | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class EcosystemGrowth:
    tvl_usd: float | None = None
    tvl_change_24h_pct: float | None = None
    stablecoin_supply_usd: float | None = None
    dex_volume_24h_usd: float | None = None
    errors: list[str] = field(default_factory=list)


def fetch_price() -> PriceInfo:
    p = PriceInfo()
    try:
        d = safe_get(COINGECKO_URL, "coingecko")["market_data"]
        p.usd = d["current_price"]["usd"]
        p.market_cap_usd = d["market_cap"]["usd"]
        p.change_24h_pct = round(d["price_change_percentage_24h"], 2) if d.get("price_change_percentage_24h") is not None else None
        p.volume_24h_usd = d["total_volume"]["usd"]
        p.ath_usd = d["ath"]["usd"]
        p.ath_change_pct = round(d["ath_change_percentage"]["usd"], 2) if d.get("ath_change_percentage", {}).get("usd") is not None else None
    except (FetchError, KeyError) as e:
        p.errors.append(str(e))
    return p


def fetch_ecosystem_growth() -> EcosystemGrowth:
    g = EcosystemGrowth()

    try:
        series = safe_get(DEFILLAMA_TVL_URL, "defillama_tvl")
        if series:
            g.tvl_usd = round(series[-1]["tvl"], 2)
            if len(series) >= 2 and series[-2]["tvl"]:
                g.tvl_change_24h_pct = round(100 * (series[-1]["tvl"] - series[-2]["tvl"]) / series[-2]["tvl"], 2)
    except (FetchError, KeyError, IndexError) as e:
        g.errors.append(f"tvl: {e}")

    try:
        chains = safe_get(DEFILLAMA_STABLECOINS_URL, "defillama_stablecoins")
        solana = next((c for c in chains if c.get("name") == "Solana"), None)
        if solana:
            g.stablecoin_supply_usd = round(solana["totalCirculatingUSD"].get("peggedUSD", 0), 2)
    except (FetchError, KeyError, StopIteration) as e:
        g.errors.append(f"stablecoins: {e}")

    try:
        dex = safe_get(DEFILLAMA_DEX_URL, "defillama_dex")
        g.dex_volume_24h_usd = round(dex.get("total24h", 0), 2) if dex.get("total24h") is not None else None
    except (FetchError, KeyError) as e:
        g.errors.append(f"dex_volume: {e}")

    return g
