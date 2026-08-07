"""Ecosystem-level data the brief asks for by name: REV, tokenized assets,
upcoming protocol upgrades, and release news.

Each of these is fetched from a source that needs no API key:

- **REV (Real Economic Value)** -- DeFiLlama's fees endpoint for the Solana
  chain. This is the network's actual fee revenue, which is what REV measures.
- **Tokenized assets / equities** -- DeFiLlama's protocol list filtered to
  RWA on Solana. This is where Ondo Global Markets, BlackRock BUIDL and the
  tokenized-equity venues surface.
- **Upcoming upgrades** -- the official `solana-improvement-documents` repo on
  GitHub. Open SIMD pull requests *are* the upgrade pipeline, so reading them
  directly is more current than any secondhand summary. Covers the Alpenglow
  and SIMD-#### items named in the brief.
- **Release news** -- GitHub releases of `anza-xyz/agave`, the validator client
  now maintained in place of `solana-labs/solana` (whose last release was
  v1.18.26 in 2024 -- pinning to it would silently report stale news).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .http_client import FetchError, safe_get

FEES_URL = "https://api.llama.fi/overview/fees/solana"
PROTOCOLS_URL = "https://api.llama.fi/protocols"
SIMD_PRS_URL = "https://api.github.com/repos/solana-foundation/solana-improvement-documents/pulls?state=open&per_page=15&sort=updated&direction=desc"
AGAVE_RELEASES_URL = "https://api.github.com/repos/anza-xyz/agave/releases?per_page=5"


@dataclass
class RealEconomicValue:
    fees_24h_usd: float | None = None
    fees_7d_usd: float | None = None
    fees_30d_usd: float | None = None
    annualized_usd: float | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class TokenizedAssets:
    rwa_total_tvl_usd: float | None = None
    rwa_protocol_count: int = 0
    top_rwa: list[dict] = field(default_factory=list)
    liquid_staking_tvl_usd: float | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class UpcomingUpgrades:
    open_simds: list[dict] = field(default_factory=list)
    releases: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fetch_rev() -> RealEconomicValue:
    rev = RealEconomicValue()
    try:
        d = safe_get(FEES_URL, "defillama_fees")
        rev.fees_24h_usd = round(d["total24h"], 2) if d.get("total24h") is not None else None
        rev.fees_7d_usd = round(d["total7d"], 2) if d.get("total7d") is not None else None
        rev.fees_30d_usd = round(d["total30d"], 2) if d.get("total30d") is not None else None
        if rev.fees_24h_usd is not None:
            rev.annualized_usd = round(rev.fees_24h_usd * 365, 2)
    except (FetchError, KeyError, TypeError) as e:
        rev.errors.append(str(e))
    return rev


def fetch_tokenized_assets() -> TokenizedAssets:
    ta = TokenizedAssets()
    try:
        protocols = safe_get(PROTOCOLS_URL, "defillama_protocols")
        on_solana = [p for p in protocols if "Solana" in (p.get("chains") or [])]

        rwa = [p for p in on_solana if p.get("category") == "RWA"]
        ta.rwa_protocol_count = len(rwa)
        ta.rwa_total_tvl_usd = round(sum(p.get("tvl") or 0 for p in rwa), 2)
        ta.top_rwa = [
            {"name": p["name"], "tvl_usd": round(p.get("tvl") or 0, 2)}
            for p in sorted(rwa, key=lambda x: -(x.get("tvl") or 0))[:8]
        ]

        lst = [p for p in on_solana if p.get("category") == "Liquid Staking"]
        ta.liquid_staking_tvl_usd = round(sum(p.get("tvl") or 0 for p in lst), 2)
    except (FetchError, KeyError, TypeError) as e:
        ta.errors.append(str(e))
    return ta


def fetch_upcoming_upgrades() -> UpcomingUpgrades:
    up = UpcomingUpgrades()
    try:
        prs = safe_get(SIMD_PRS_URL, "github_simds")
        up.open_simds = [
            {
                "number": pr["number"],
                "title": pr["title"][:120],
                "url": pr["html_url"],
                "updated_at": pr["updated_at"][:10],
            }
            for pr in prs
        ]
    except (FetchError, KeyError, TypeError) as e:
        up.errors.append(f"simds: {e}")

    try:
        rels = safe_get(AGAVE_RELEASES_URL, "github_agave_releases")
        up.releases = [
            {
                "tag": r["tag_name"],
                "name": (r.get("name") or "")[:80],
                "published_at": (r.get("published_at") or "")[:10],
                "url": r["html_url"],
                "prerelease": r.get("prerelease", False),
            }
            for r in rels
        ]
    except (FetchError, KeyError, TypeError) as e:
        up.errors.append(f"releases: {e}")

    return up
