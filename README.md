# Solana Ecosystem Report & Interactive Dashboard

An auto-updating report on the state of the Solana network — performance,
validators, fees, REV, tokenized assets, protocol upgrades — with statistical
anomaly detection and an interactive dark-theme dashboard.

**Zero dependencies. No API keys. `git clone` and run.**

Built for the *"Develop Solana Ecosystem Auto-Updating Report & Interactive
Dashboard"* bounty (Superteam Canada).

---

## Quickstart

```bash
git clone <this-repo-url>
cd solana-ecosystem-report
python -m src.main
```

No virtual environment. No `requirements.txt`. No `pip install`. Python 3.10+
and nothing else — every HTTP call goes through
[`src/http_client.py`](src/http_client.py), built on `urllib` from the standard
library.

A live sample run is committed in [`samples/`](samples/) — open
[`samples/dashboard.html`](samples/dashboard.html) straight from disk.

```bash
python -m src.main --interval 900          # refresh every 15 minutes
python -m src.main --rpc-url <your-rpc>    # swap the RPC endpoint
```

Outputs land in `./output/`:

| File | Purpose |
|---|---|
| `dashboard.html` | Interactive dashboard — charts, sortable tables, tooltips. Self-contained, opens offline |
| `report.md` | Human-readable Markdown report |
| `report.json` | Machine-readable structured snapshot |
| `snapshots.jsonl` | Accumulated history — what makes throughput measurable between runs |

---

## What makes this different

### 1. Genuinely zero dependencies — and it's verifiable

Most "no dependency" claims quietly break the moment charts are needed. The SVG
charts in [`src/charts.py`](src/charts.py) are generated as raw path geometry —
no Chart.js, no D3, no CDN. The dashboard loads **zero external resources**, so
it renders with the network unplugged.

Verify it yourself:

```bash
python -c "import ast,pathlib,sys; m=set()
for f in pathlib.Path('src').glob('*.py'):
    for n in ast.walk(ast.parse(f.read_text())):
        if isinstance(n,ast.Import): [m.add(a.name.split('.')[0]) for a in n.names]
        elif isinstance(n,ast.ImportFrom) and n.level==0 and n.module: m.add(n.module.split('.')[0])
print('Outside stdlib:', sorted(m - sys.stdlib_module_names) or 'NONE')"
```

### 2. Anomaly detection measured against history, not invented thresholds

An earlier draft of this project flagged things like *"TPS below 1000"*. That
number was picked by feel — nothing justified 1000 over 800 or 1500, and a
reviewer had no way to tell whether the flag meant anything.

[`src/anomaly.py`](src/anomaly.py) now computes **z-scores against each metric's
own trailing 30 observations**, so "anomalous" means "far from what this metric
actually does". The only free parameters are the conventional 2σ / 3σ cutoffs,
not values tuned to make the output look good.

Where no historical feed exists, checks are **structural and labelled as such**:
delinquent stake above 33% matters because Solana needs >2/3 of stake voting to
finalize — a protocol property, not a guess. Every anomaly in the output carries
a `basis` field stating how it was determined.

### 3. Throughput is measured, not sampled

`getRecentPerformanceSamples` gives a 60-second window that swings by hundreds
of TPS between calls. This report averages 10 samples for the instantaneous
figure **and** persists each run's cumulative transaction counter to
`snapshots.jsonl`, so consecutive runs yield throughput measured across the real
elapsed interval — with the measurement window stated in the output.

### 4. Upgrade tracking reads the actual source

"Upcoming upgrades" comes from open pull requests on the official
[`solana-improvement-documents`](https://github.com/solana-foundation/solana-improvement-documents)
repository — the SIMD pipeline *is* the upgrade pipeline, so this is more
current than any secondhand summary and needs no key.

Client releases come from `anza-xyz/agave`, the validator client now maintained
in place of `solana-labs/solana` — whose last release was v1.18.26 in 2024.
Pinning to the old repo would have silently reported two-year-old news as current.

---

## Coverage against the brief

| Requested | Status | Source |
|---|---|---|
| Network performance: TPS, slot time, block height, epoch progress | Covered | RPC `getEpochInfo`, `getRecentPerformanceSamples`, `getBlockTime` |
| Validator status: active/delinquent, stake distribution, top by stake, commission, delinquency alerts | Covered | RPC `getVoteAccounts` |
| SOL price, market cap, volume, ATH | Covered | CoinGecko |
| Stablecoin supply, DEX volume, TVL | Covered | DeFiLlama |
| **Real Economic Value (REV)** | Covered | DeFiLlama chain fees — 24h / 7d / 30d / annualized |
| **Median transaction fees** | Covered | RPC `getRecentPrioritizationFees` — median, mean, p95, max |
| **Tokenized asset volumes (especially equities)** | Covered | DeFiLlama RWA protocols on Solana |
| **Upcoming upgrades (Alpenglow, SIMD-####)** | Covered | GitHub API on the SIMD repository |
| **Ecosystem news** | Covered | Agave client releases |
| Anomaly detection | Covered | z-scores + structural + cross-source divergence |
| Interactive HTML dashboard, dark theme | Covered | Sortable tables, 7 SVG charts, hover tooltips |
| Markdown report | Covered | `output/report.md` |
| Machine-readable JSON | Covered | `output/report.json` |
| Configurable refresh interval | Covered | `--interval` |
| No API keys / no dependencies | Covered | stdlib only, verifiable above |
| **Daily active addresses** | **Not covered** | See below |
| **Dune Analytics** | **Not covered** | See below |
| **Twitter sentiment** | **Not covered** | See below |

### The three gaps, stated plainly

Rather than leave a reviewer to discover these:

- **Daily active addresses** — no key-less public feed exists for it. Deriving
  it properly needs a full indexer over account activity, which cannot be done
  from RPC alone without hammering the public endpoint. Transaction throughput
  is reported instead and is explicitly labelled as *throughput*, not as users,
  because conflating the two would be misleading.
- **Dune Analytics** — its API requires an authenticated key, which directly
  conflicts with the no-key design the brief marks as preferred. Every metric
  Dune would supply here is sourced from DeFiLlama or direct RPC instead.
- **Twitter/X sentiment** — requires paid API access as of 2026. Protocol news
  is sourced from the SIMD repository and client releases instead, which is
  where upgrade decisions actually happen rather than where they're discussed.

---

## Resilience

Every data source fails independently. Each section carries its own
`errors: list[str]`; if CoinGecko times out, the validator and network sections
still render, and both the Markdown and JSON outputs name exactly which source
failed. A stalled feed never silently passes off a stale number as live.

Unit conversion happens once, at the fetch boundary
(`LAMPORTS_PER_SOL` in [`src/solana_rpc.py`](src/solana_rpc.py)), so there is
exactly one place it can go wrong.

---

## Project layout

```
src/
  http_client.py   stdlib-only HTTP (urllib), per-source error isolation
  solana_rpc.py    network performance, fees, validators, supply
  market_data.py   price, TVL, stablecoins, DEX volume
  history.py       time series + z-score machinery
  ecosystem.py     REV, tokenized assets, SIMDs, client releases
  snapshots.py     JSONL persistence, throughput between runs
  anomaly.py       statistical + structural + correlation detection
  charts.py        hand-rolled SVG charts, no library
  render.py        JSON / Markdown / interactive HTML
  main.py          CLI entry point
samples/           a committed live run
output/            generated per run (gitignored)
```
