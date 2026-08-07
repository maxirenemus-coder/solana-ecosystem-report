"""Renders the snapshot into JSON, Markdown, and an interactive HTML dashboard."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from . import charts


def _num(v, suffix="", decimals=2):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:,.{decimals}f}{suffix}"
    return f"{v:,}{suffix}"


def _usd(v, decimals=0):
    return "n/a" if v is None else f"${v:,.{decimals}f}"


def build_snapshot(perf, validators, supply, price, growth, fees, rev,
                   tokenized, upgrades, anomalies, history, activity) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "network_performance": asdict(perf),
        "fees": asdict(fees),
        "validator_status": asdict(validators),
        "supply": asdict(supply),
        "price": asdict(price),
        "ecosystem_growth": asdict(growth),
        "real_economic_value": asdict(rev),
        "tokenized_assets": asdict(tokenized),
        "upcoming_upgrades": asdict(upgrades),
        "network_activity": asdict(activity),
        "anomalies": [asdict(a) for a in anomalies],
        "history_summary": {
            "price_points": len(history.price),
            "tvl_points": len(history.tvl),
            "dex_volume_points": len(history.dex_volume),
            "price_zscore_30d": history.price.zscore(30),
            "tvl_zscore_30d": history.tvl.zscore(30),
            "errors": history.errors,
        },
    }


def collect_errors(s: dict) -> list[str]:
    keys = ("network_performance", "fees", "validator_status", "supply", "price",
            "ecosystem_growth", "real_economic_value", "tokenized_assets",
            "upcoming_upgrades")
    out = []
    for k in keys:
        out += [f"{k}: {e}" for e in (s.get(k, {}).get("errors") or [])]
    out += [f"history: {e}" for e in (s.get("history_summary", {}).get("errors") or [])]
    return out


def render_json(snapshot: dict) -> str:
    return json.dumps(snapshot, indent=2)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def render_markdown(s: dict) -> str:
    p, v, sup = s["network_performance"], s["validator_status"], s["supply"]
    pr, g, f = s["price"], s["ecosystem_growth"], s["fees"]
    rev, ta, up = s["real_economic_value"], s["tokenized_assets"], s["upcoming_upgrades"]
    act, an = s["network_activity"], s["anomalies"]

    L = [
        "# Solana Ecosystem Report",
        "",
        f"_Generated {s['generated_at']} · all data from key-less public sources_",
        "",
        "## Network Performance",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cluster health | {p['health'] or 'n/a'} |",
        f"| TPS (10-sample avg) | {_num(p['tps'], decimals=1)} |",
        f"| Non-vote TPS | {_num(p['non_vote_tps'], decimals=1)} |",
        f"| Avg slot time | {_num(p['avg_slot_time_ms'], ' ms', 0)} |",
        f"| Current slot | {_num(p['slot'], decimals=0)} |",
        f"| Block height | {_num(p['block_height'], decimals=0)} |",
        f"| Latest block time | {p['block_time_utc'] or 'n/a'} |",
        f"| Epoch | {_num(p['epoch'], decimals=0)} ({_num(p['epoch_progress_pct'], '%')} complete) |",
        f"| Epoch ends in | {_num(p['epoch_eta_hours'], ' h', 1)} |",
        f"| Cumulative transactions | {_num(p['transaction_count'], decimals=0)} |",
        "",
        "### Measured throughput between runs",
        "",
    ]
    if act.get("tps_measured") is not None:
        L += [
            f"- **{_num(act['tps_measured'], decimals=1)} TPS** measured over {_num(act['seconds_elapsed'], ' s', 0)}",
            f"- {_num(act['transactions'], decimals=0)} transactions across {_num(act['slots_elapsed'], decimals=0)} slots",
            f"- Projected daily volume: {_num(act['projected_daily_transactions'], decimals=0)} transactions",
            f"- _{act['basis']}_",
        ]
    else:
        L.append(f"- {act.get('basis', 'not available')}")

    L += [
        "",
        "## Transaction Fees",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Median priority fee | {_num(f['median_priority_fee'])} micro-lamports/CU |",
        f"| Mean priority fee | {_num(f['mean_priority_fee'])} |",
        f"| 95th percentile | {_num(f['p95_priority_fee'])} |",
        f"| Max observed | {_num(f['max_priority_fee'])} |",
        f"| Slots sampled | {_num(f['samples'], decimals=0)} ({_num(f['nonzero_samples'], decimals=0)} with fees) |",
        "",
        f"> {f['congestion_note'] or 'n/a'}",
        "",
        "## Real Economic Value (REV)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Network fees, 24h | {_usd(rev['fees_24h_usd'])} |",
        f"| Network fees, 7d | {_usd(rev['fees_7d_usd'])} |",
        f"| Network fees, 30d | {_usd(rev['fees_30d_usd'])} |",
        f"| Annualized run-rate | {_usd(rev['annualized_usd'])} |",
        "",
        "## Validator Status",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Active validators | {_num(v['active_count'], decimals=0)} |",
        f"| Delinquent validators | {_num(v['delinquent_count'], decimals=0)} |",
        f"| Active stake | {_num(v['total_active_stake_sol'], ' SOL')} |",
        f"| Delinquent stake | {_num(v['total_delinquent_stake_sol'], ' SOL')} ({_num(v['delinquent_stake_pct'], '%')}) |",
        f"| Avg commission | {_num(v['avg_commission_pct'], '%')} |",
        "",
        "### Top validators by stake",
        "",
        "| Vote Account | Stake (SOL) | Commission |",
        "|---|---|---|",
    ]
    for tv in v["top_validators"]:
        L.append(f"| `{tv['votePubkey']}` | {_num(tv['stake_sol'])} | {tv['commission_pct']}% |")

    L += [
        "",
        "## Economic Indicators",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| SOL price | {_usd(pr['usd'], 2)} ({_num(pr['change_24h_pct'], '%')} 24h) |",
        f"| Market cap | {_usd(pr['market_cap_usd'])} |",
        f"| 24h volume | {_usd(pr['volume_24h_usd'])} |",
        f"| All-time high | {_usd(pr['ath_usd'], 2)} ({_num(pr['ath_change_pct'], '%')} from ATH) |",
        f"| Circulating supply | {_num(sup['circulating_sol'], ' SOL')} |",
        f"| Total supply | {_num(sup['total_sol'], ' SOL')} |",
        f"| Ecosystem TVL | {_usd(g['tvl_usd'])} ({_num(g['tvl_change_24h_pct'], '%')} 24h) |",
        f"| Stablecoin supply | {_usd(g['stablecoin_supply_usd'])} |",
        f"| DEX volume, 24h | {_usd(g['dex_volume_24h_usd'])} |",
        "",
        "## Tokenized Assets & Liquid Staking",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| RWA protocols on Solana | {_num(ta['rwa_protocol_count'], decimals=0)} |",
        f"| RWA total TVL | {_usd(ta['rwa_total_tvl_usd'])} |",
        f"| Liquid staking TVL | {_usd(ta['liquid_staking_tvl_usd'])} |",
        "",
        "### Largest tokenized-asset venues",
        "",
        "| Protocol | TVL |",
        "|---|---|",
    ]
    for r in ta["top_rwa"]:
        L.append(f"| {r['name']} | {_usd(r['tvl_usd'])} |")

    L += [
        "",
        "## Upcoming Upgrades & Releases",
        "",
        "Pulled live from the official `solana-improvement-documents` repository",
        "and the Agave validator client releases.",
        "",
        "### Open SIMDs (protocol changes in flight)",
        "",
    ]
    if up["open_simds"]:
        L += ["| SIMD | Title | Updated |", "|---|---|---|"]
        for sd in up["open_simds"][:12]:
            L.append(f"| [#{sd['number']}]({sd['url']}) | {sd['title']} | {sd['updated_at']} |")
    else:
        L.append("_No data this run._")

    L += ["", "### Recent Agave client releases", ""]
    if up["releases"]:
        L += ["| Version | Date | Type |", "|---|---|---|"]
        for r in up["releases"]:
            kind = "pre-release" if r["prerelease"] else "stable"
            L.append(f"| [{r['tag']}]({r['url']}) | {r['published_at']} | {kind} |")
    else:
        L.append("_No data this run._")

    L += ["", "## Anomalies", ""]
    if an:
        for a in an:
            L.append(f"- **[{a['severity'].upper()}]** {a['message']}")
            L.append(f"  - _Basis: {a['basis']}_")
    else:
        L.append("- None detected. All monitored metrics sit within their measured historical range.")

    errors = collect_errors(s)
    if errors:
        L += ["", "## Data Source Errors (this run)", ""]
        L += [f"- {e}" for e in errors]

    L += [
        "",
        "## Methodology & Coverage",
        "",
        "- Anomalies are z-scores against each metric's own trailing 30 observations,",
        "  not hand-picked thresholds. Structural checks (delinquent stake, slot time)",
        "  are derived from documented protocol properties and labelled as such.",
        "- Throughput between runs is measured from the cumulative transaction counter,",
        "  not extrapolated from a single sampling window.",
        "- Every figure above comes from a public endpoint requiring no API key.",
        "",
        "### Not covered, stated plainly",
        "",
        "- **Daily active addresses**: no key-less public feed exists. Computing it",
        "  requires a full indexer over account activity, which is out of scope for a",
        "  dependency-free report. Transaction throughput above is the closest",
        "  honest proxy, and is labelled as throughput rather than as users.",
        "- **Dune Analytics**: its API requires an authenticated key, which conflicts",
        "  with this report's no-key design. Every metric Dune would supply here is",
        "  sourced from DeFiLlama or direct RPC instead.",
        "- **Twitter/X sentiment**: requires paid API access. Protocol news is instead",
        "  sourced from the SIMD repository and client releases, which is where",
        "  upgrades are actually decided.",
        "",
    ]
    return "\n".join(L)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def render_html(s: dict, history) -> str:
    p, v, sup = s["network_performance"], s["validator_status"], s["supply"]
    pr, g, f = s["price"], s["ecosystem_growth"], s["fees"]
    rev, ta, up = s["real_economic_value"], s["tokenized_assets"], s["upcoming_upgrades"]
    act, an = s["network_activity"], s["anomalies"]

    price_chart = charts.line_chart(history.price.timestamps, history.price.values,
                                    "SOL price (90d)", "$", color="#14F195")
    tvl_chart = charts.line_chart(history.tvl.timestamps, history.tvl.values,
                                  "Solana TVL (180d)", "$", color="#9945FF")
    dex_chart = charts.line_chart(history.dex_volume.timestamps, history.dex_volume.values,
                                  "DEX volume (180d)", "$", color="#4da3ff")

    price_spark = charts.sparkline(history.price.values[-30:] or [0, 0], color="#14F195")
    tvl_spark = charts.sparkline(history.tvl.values[-30:] or [0, 0], color="#9945FF")

    top = v["top_validators"]
    stake_bars = charts.bar_chart(
        [t["votePubkey"][:14] + "…" for t in top],
        [t["stake_sol"] for t in top],
    )
    ring = charts.progress_ring(p["epoch_progress_pct"] or 0)

    validator_rows = "\n".join(
        f'<tr><td><code>{t["votePubkey"]}</code></td>'
        f'<td data-sort="{t["stake_sol"]}">{_num(t["stake_sol"])}</td>'
        f'<td data-sort="{t["commission_pct"]}">{t["commission_pct"]}%</td></tr>'
        for t in top
    ) or "<tr><td colspan='3'>No data</td></tr>"

    simd_rows = "\n".join(
        f'<tr><td><a href="{sd["url"]}" target="_blank" rel="noopener">#{sd["number"]}</a></td>'
        f'<td>{_esc(sd["title"])}</td><td>{sd["updated_at"]}</td></tr>'
        for sd in up["open_simds"][:12]
    ) or "<tr><td colspan='3'>No data</td></tr>"

    release_rows = "\n".join(
        f'<tr><td><a href="{r["url"]}" target="_blank" rel="noopener">{r["tag"]}</a></td>'
        f'<td>{r["published_at"]}</td>'
        f'<td>{"pre-release" if r["prerelease"] else "stable"}</td></tr>'
        for r in up["releases"]
    ) or "<tr><td colspan='3'>No data</td></tr>"

    rwa_rows = "\n".join(
        f'<tr><td>{_esc(r["name"])}</td><td>{_usd(r["tvl_usd"])}</td></tr>'
        for r in ta["top_rwa"]
    ) or "<tr><td colspan='2'>No data</td></tr>"

    if an:
        anomaly_html = "".join(
            f'<div class="anomaly {a["severity"]}"><div class="a-msg">{_esc(a["message"])}</div>'
            f'<div class="a-basis">{_esc(a["basis"])}</div></div>'
            for a in an
        )
    else:
        anomaly_html = ('<div class="anomaly none"><div class="a-msg">No anomalies detected.</div>'
                        '<div class="a-basis">All monitored metrics sit within their measured '
                        '30-observation historical range.</div></div>')

    errors = collect_errors(s)
    error_html = ""
    if errors:
        error_html = ('<div class="section"><h2>Data source errors this run</h2>'
                      + "".join(f'<div class="err">{_esc(e)}</div>' for e in errors) + "</div>")

    activity_html = (
        f'<div class="metric"><span>Measured TPS</span><span class="v">{_num(act["tps_measured"], decimals=1)}</span></div>'
        f'<div class="metric"><span>Txns since last run</span><span class="v">{_num(act["transactions"], decimals=0)}</span></div>'
        f'<div class="metric"><span>Projected daily txns</span><span class="v">{_num(act["projected_daily_transactions"], decimals=0)}</span></div>'
        if act.get("tps_measured") is not None else
        f'<div class="note">{_esc(act.get("basis", "not available"))}</div>'
    )

    return _HTML.format(
        generated_at=s["generated_at"],
        health=p["health"] or "n/a",
        health_class="ok" if p["health"] == "ok" else "bad",
        tps=_num(p["tps"], decimals=1),
        non_vote_tps=_num(p["non_vote_tps"], decimals=1),
        slot_time=_num(p["avg_slot_time_ms"], " ms", 0),
        slot=_num(p["slot"], decimals=0),
        block_height=_num(p["block_height"], decimals=0),
        epoch=_num(p["epoch"], decimals=0),
        epoch_eta=_num(p["epoch_eta_hours"], " h", 1),
        ring=ring,
        activity_html=activity_html,
        median_fee=_num(f["median_priority_fee"]),
        p95_fee=_num(f["p95_priority_fee"]),
        max_fee=_num(f["max_priority_fee"]),
        fee_note=_esc(f["congestion_note"] or ""),
        rev_24h=_usd(rev["fees_24h_usd"]),
        rev_7d=_usd(rev["fees_7d_usd"]),
        rev_annual=_usd(rev["annualized_usd"]),
        active_validators=_num(v["active_count"], decimals=0),
        delinquent_validators=_num(v["delinquent_count"], decimals=0),
        delinquent_pct=_num(v["delinquent_stake_pct"], "%"),
        active_stake=_num(v["total_active_stake_sol"], " SOL", 0),
        avg_commission=_num(v["avg_commission_pct"], "%"),
        price=_usd(pr["usd"], 2),
        change_24h=_num(pr["change_24h_pct"], "%"),
        change_class="up" if (pr["change_24h_pct"] or 0) >= 0 else "down",
        market_cap=_usd(pr["market_cap_usd"]),
        volume_24h=_usd(pr["volume_24h_usd"]),
        ath=_usd(pr["ath_usd"], 2),
        ath_change=_num(pr["ath_change_pct"], "%"),
        circulating=_num(sup["circulating_sol"], " SOL", 0),
        tvl=_usd(g["tvl_usd"]),
        tvl_change=_num(g["tvl_change_24h_pct"], "%"),
        stablecoins=_usd(g["stablecoin_supply_usd"]),
        dex_volume=_usd(g["dex_volume_24h_usd"]),
        rwa_tvl=_usd(ta["rwa_total_tvl_usd"]),
        rwa_count=_num(ta["rwa_protocol_count"], decimals=0),
        lst_tvl=_usd(ta["liquid_staking_tvl_usd"]),
        price_spark=price_spark,
        tvl_spark=tvl_spark,
        price_chart=price_chart,
        tvl_chart=tvl_chart,
        dex_chart=dex_chart,
        stake_bars=stake_bars,
        validator_rows=validator_rows,
        simd_rows=simd_rows,
        release_rows=release_rows,
        rwa_rows=rwa_rows,
        anomaly_html=anomaly_html,
        error_html=error_html,
    )


def _esc(t) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solana Ecosystem Dashboard</title>
<style>
  :root {{
    --bg:#0a0d13; --panel:#12161f; --panel2:#161b26; --border:#242a38;
    --text:#e8ebf2; --muted:#8890a4; --accent:#9945FF; --green:#14F195;
    --blue:#4da3ff; --red:#ff5c6c; --amber:#f5a623;
  }}
  *{{box-sizing:border-box;}}
  body{{margin:0;padding:20px;background:var(--bg);color:var(--text);
    font-family:-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px;line-height:1.45;}}
  .wrap{{max-width:1280px;margin:0 auto;}}
  header{{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px;margin-bottom:6px;}}
  h1{{font-size:1.45rem;margin:0;letter-spacing:-0.02em;}}
  .pill{{font-size:.7rem;padding:3px 9px;border-radius:99px;text-transform:uppercase;letter-spacing:.05em;font-weight:600;}}
  .pill.ok{{background:rgba(20,241,149,.14);color:var(--green);}}
  .pill.bad{{background:rgba(255,92,108,.14);color:var(--red);}}
  .sub{{color:var(--muted);font-size:.82rem;margin-bottom:22px;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;}}
  .card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:15px;}}
  .card h2{{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
    margin:0 0 11px;font-weight:600;}}
  .metric{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
    padding:5px 0;border-bottom:1px solid rgba(36,42,56,.6);}}
  .metric:last-child{{border-bottom:none;}}
  .metric span:first-child{{color:var(--muted);font-size:.85rem;}}
  .v{{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums;}}
  .v.up{{color:var(--green);}} .v.down{{color:var(--red);}}
  .big{{font-size:1.6rem;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;}}
  .ring{{display:flex;align-items:center;gap:14px;}}
  .section{{margin-top:26px;}}
  .section h2{{font-size:.95rem;margin:0 0 12px;padding-bottom:7px;border-bottom:1px solid var(--border);}}
  .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px;}}
  .chart-box{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px;}}
  .chart-box h3{{font-size:.78rem;color:var(--muted);margin:0 0 8px;font-weight:600;
    text-transform:uppercase;letter-spacing:.05em;}}
  .chart-empty{{color:var(--muted);font-size:.85rem;padding:30px;text-align:center;}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem;}}
  th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--border);}}
  th{{color:var(--muted);font-weight:500;font-size:.75rem;text-transform:uppercase;
    letter-spacing:.04em;cursor:pointer;user-select:none;white-space:nowrap;}}
  th.sortable:hover{{color:var(--text);}}
  th::after{{content:'';}}
  th.asc::after{{content:' \\2191';color:var(--accent);}}
  th.desc::after{{content:' \\2193';color:var(--accent);}}
  tbody tr:hover{{background:rgba(153,69,255,.06);}}
  code{{color:var(--green);font-size:.78rem;font-family:ui-monospace,Menlo,monospace;}}
  a{{color:var(--blue);text-decoration:none;}} a:hover{{text-decoration:underline;}}
  .anomaly{{border-left:3px solid var(--border);padding:9px 13px;margin-bottom:8px;
    background:var(--panel2);border-radius:0 8px 8px 0;}}
  .anomaly.critical{{border-left-color:var(--red);}}
  .anomaly.warning{{border-left-color:var(--amber);}}
  .anomaly.info{{border-left-color:var(--blue);}}
  .anomaly.none{{border-left-color:var(--green);}}
  .a-msg{{font-size:.88rem;}}
  .a-basis{{font-size:.74rem;color:var(--muted);margin-top:3px;}}
  .note{{color:var(--muted);font-size:.82rem;font-style:italic;}}
  .err{{color:var(--amber);font-size:.8rem;font-family:ui-monospace,monospace;padding:3px 0;}}
  .tablewrap{{overflow-x:auto;background:var(--panel);border:1px solid var(--border);
    border-radius:12px;padding:4px 14px 10px;}}
  .two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px;}}
  footer{{margin-top:30px;padding-top:14px;border-top:1px solid var(--border);
    color:var(--muted);font-size:.78rem;}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Solana Ecosystem Dashboard</h1>
    <span class="pill {health_class}">cluster {health}</span>
  </header>
  <div class="sub">Generated {generated_at} · zero dependencies, no API keys · click any column header to sort</div>

  <div class="grid">
    <div class="card">
      <h2>SOL Price</h2>
      <div class="big">{price}</div>
      <div class="metric"><span>24h</span><span class="v {change_class}">{change_24h}</span></div>
      {price_spark}
      <div class="metric"><span>Market cap</span><span class="v">{market_cap}</span></div>
      <div class="metric"><span>24h volume</span><span class="v">{volume_24h}</span></div>
      <div class="metric"><span>ATH</span><span class="v">{ath} ({ath_change})</span></div>
    </div>

    <div class="card">
      <h2>Ecosystem TVL</h2>
      <div class="big">{tvl}</div>
      <div class="metric"><span>24h</span><span class="v">{tvl_change}</span></div>
      {tvl_spark}
      <div class="metric"><span>Stablecoin supply</span><span class="v">{stablecoins}</span></div>
      <div class="metric"><span>DEX volume 24h</span><span class="v">{dex_volume}</span></div>
      <div class="metric"><span>Circulating</span><span class="v">{circulating}</span></div>
    </div>

    <div class="card">
      <h2>Network Performance</h2>
      <div class="ring">
        {ring}
        <div style="flex:1">
          <div class="metric"><span>Epoch</span><span class="v">{epoch}</span></div>
          <div class="metric"><span>Ends in</span><span class="v">{epoch_eta}</span></div>
        </div>
      </div>
      <div class="metric"><span>TPS (10-sample)</span><span class="v">{tps}</span></div>
      <div class="metric"><span>Non-vote TPS</span><span class="v">{non_vote_tps}</span></div>
      <div class="metric"><span>Slot time</span><span class="v">{slot_time}</span></div>
      <div class="metric"><span>Slot</span><span class="v">{slot}</span></div>
      <div class="metric"><span>Block height</span><span class="v">{block_height}</span></div>
    </div>

    <div class="card">
      <h2>Measured Throughput</h2>
      {activity_html}
    </div>

    <div class="card">
      <h2>Validators</h2>
      <div class="big">{active_validators}</div>
      <div class="metric"><span>Delinquent</span><span class="v">{delinquent_validators}</span></div>
      <div class="metric"><span>Delinquent stake</span><span class="v">{delinquent_pct}</span></div>
      <div class="metric"><span>Active stake</span><span class="v">{active_stake}</span></div>
      <div class="metric"><span>Avg commission</span><span class="v">{avg_commission}</span></div>
    </div>

    <div class="card">
      <h2>Real Economic Value</h2>
      <div class="big">{rev_24h}</div>
      <div class="metric"><span>Fees 24h</span><span class="v">{rev_24h}</span></div>
      <div class="metric"><span>Fees 7d</span><span class="v">{rev_7d}</span></div>
      <div class="metric"><span>Annualized</span><span class="v">{rev_annual}</span></div>
    </div>

    <div class="card">
      <h2>Priority Fees</h2>
      <div class="metric"><span>Median</span><span class="v">{median_fee}</span></div>
      <div class="metric"><span>95th pct</span><span class="v">{p95_fee}</span></div>
      <div class="metric"><span>Max</span><span class="v">{max_fee}</span></div>
      <div class="note" style="margin-top:8px">{fee_note}</div>
    </div>

    <div class="card">
      <h2>Tokenized Assets</h2>
      <div class="big">{rwa_tvl}</div>
      <div class="metric"><span>RWA protocols</span><span class="v">{rwa_count}</span></div>
      <div class="metric"><span>Liquid staking TVL</span><span class="v">{lst_tvl}</span></div>
    </div>
  </div>

  <div class="section">
    <h2>Historical Trends</h2>
    <div class="charts">
      <div class="chart-box"><h3>SOL Price · 90 days</h3>{price_chart}</div>
      <div class="chart-box"><h3>Ecosystem TVL · 180 days</h3>{tvl_chart}</div>
      <div class="chart-box"><h3>DEX Volume · 180 days</h3>{dex_chart}</div>
      <div class="chart-box"><h3>Stake Distribution · Top Validators</h3>{stake_bars}</div>
    </div>
  </div>

  <div class="section">
    <h2>Anomaly Detection</h2>
    {anomaly_html}
  </div>

  <div class="section">
    <h2>Top Validators by Stake</h2>
    <div class="tablewrap">
      <table data-sortable>
        <thead><tr><th class="sortable">Vote Account</th><th class="sortable">Stake (SOL)</th><th class="sortable">Commission</th></tr></thead>
        <tbody>{validator_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="section two">
    <div>
      <h2>Open SIMDs · Protocol Changes In Flight</h2>
      <div class="tablewrap">
        <table data-sortable>
          <thead><tr><th class="sortable">SIMD</th><th class="sortable">Title</th><th class="sortable">Updated</th></tr></thead>
          <tbody>{simd_rows}</tbody>
        </table>
      </div>
    </div>
    <div>
      <h2>Agave Client Releases</h2>
      <div class="tablewrap">
        <table data-sortable>
          <thead><tr><th class="sortable">Version</th><th class="sortable">Date</th><th class="sortable">Type</th></tr></thead>
          <tbody>{release_rows}</tbody>
        </table>
      </div>
      <h2 style="margin-top:20px">Largest Tokenized-Asset Venues</h2>
      <div class="tablewrap">
        <table data-sortable>
          <thead><tr><th class="sortable">Protocol</th><th class="sortable">TVL</th></tr></thead>
          <tbody>{rwa_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  {error_html}

  <footer>
    Every figure sourced from public, key-less endpoints: Solana mainnet RPC,
    CoinGecko, DeFiLlama, and the GitHub API. Anomalies are z-scores against each
    metric's own trailing history, not hand-picked thresholds.
  </footer>
</div>

<script>
// Column sorting. Vanilla JS, no library -- consistent with the
// zero-dependency constraint the rest of the project holds to.
document.querySelectorAll('table[data-sortable]').forEach(function (table) {{
  var headers = table.querySelectorAll('th.sortable');
  headers.forEach(function (th, idx) {{
    th.addEventListener('click', function () {{
      var tbody = table.querySelector('tbody');
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      var asc = !th.classList.contains('asc');
      headers.forEach(function (h) {{ h.classList.remove('asc', 'desc'); }});
      th.classList.add(asc ? 'asc' : 'desc');

      rows.sort(function (a, b) {{
        var ca = a.children[idx], cb = b.children[idx];
        if (!ca || !cb) return 0;
        // data-sort carries the raw numeric value so "16,882,234.36" sorts
        // numerically instead of lexically.
        var va = ca.dataset.sort !== undefined ? parseFloat(ca.dataset.sort) : NaN;
        var vb = cb.dataset.sort !== undefined ? parseFloat(cb.dataset.sort) : NaN;
        if (!isNaN(va) && !isNaN(vb)) return asc ? va - vb : vb - va;
        var ta = ca.textContent.trim(), tb = cb.textContent.trim();
        return asc ? ta.localeCompare(tb) : tb.localeCompare(ta);
      }});
      rows.forEach(function (r) {{ tbody.appendChild(r); }});
    }});
  }});
}});
</script>
</body>
</html>
"""
