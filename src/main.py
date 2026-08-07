"""Entry point: fetch every source, detect anomalies, render, persist.

    python -m src.main                    # single run, writes to ./output
    python -m src.main --interval 900     # refresh every 15 minutes
    python -m src.main --rpc-url <url>    # use a different Solana RPC
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import anomaly, ecosystem, history, market_data, render, snapshots, solana_rpc

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
SNAPSHOT_FILE = ROOT / "output" / "snapshots.jsonl"


def run_once(rpc_url: str, output_dir: Path, snapshot_file: Path,
             quiet: bool = False) -> dict:
    def say(msg):
        if not quiet:
            print(msg, file=sys.stderr)

    say("[1/8] Network performance (RPC)...")
    perf = solana_rpc.fetch_network_performance(rpc_url)
    say("[2/8] Prioritization fees (RPC)...")
    fees = solana_rpc.fetch_fees(rpc_url)
    say("[3/8] Validators (RPC)...")
    validators = solana_rpc.fetch_validator_status(rpc_url)
    say("[4/8] Supply (RPC)...")
    supply = solana_rpc.fetch_supply(rpc_url)
    say("[5/8] Price and ecosystem growth...")
    price = market_data.fetch_price()
    growth = market_data.fetch_ecosystem_growth()
    say("[6/8] Historical series...")
    hist = history.fetch_history()
    say("[7/8] REV, tokenized assets, upgrades...")
    rev = ecosystem.fetch_rev()
    tokenized = ecosystem.fetch_tokenized_assets()
    upgrades = ecosystem.fetch_upcoming_upgrades()

    say("[8/8] Anomaly detection and rendering...")
    findings = anomaly.detect(perf, validators, price, growth, hist)

    prior = snapshots.load(snapshot_file)
    partial = render.build_snapshot(perf, validators, supply, price, growth, fees,
                                    rev, tokenized, upgrades, findings, hist,
                                    snapshots.ActivityDelta())
    activity = snapshots.compute_activity(prior, partial)
    snapshot = render.build_snapshot(perf, validators, supply, price, growth, fees,
                                     rev, tokenized, upgrades, findings, hist, activity)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(render.render_json(snapshot), encoding="utf-8")
    (output_dir / "report.md").write_text(render.render_markdown(snapshot), encoding="utf-8")
    (output_dir / "dashboard.html").write_text(render.render_html(snapshot, hist), encoding="utf-8")
    snapshots.append(snapshot_file, snapshot)

    errors = render.collect_errors(snapshot)
    say(f"Done. {len(findings)} anomalies, {len(errors)} source errors, "
        f"{len(prior) + 1} snapshots stored. Output in {output_dir}")
    for e in errors:
        say(f"  ! {e}")
    return snapshot


def main() -> int:
    ap = argparse.ArgumentParser(description="Solana ecosystem auto-updating report")
    ap.add_argument("--rpc-url", default=solana_rpc.DEFAULT_RPC,
                    help="Solana RPC endpoint (default: public mainnet-beta)")
    ap.add_argument("--output-dir", default=str(OUTPUT_DIR))
    ap.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE),
                    help="JSONL history used to measure throughput between runs")
    ap.add_argument("--interval", type=int, default=0,
                    help="Seconds between refreshes. 0 (default) runs once and exits.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out, snap = Path(args.output_dir), Path(args.snapshot_file)

    if args.interval <= 0:
        run_once(args.rpc_url, out, snap, args.quiet)
        return 0

    print(f"Refreshing every {args.interval}s. Ctrl+C to stop.", file=sys.stderr)
    while True:
        try:
            run_once(args.rpc_url, out, snap, args.quiet)
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 0
        except Exception as e:
            print(f"Run failed, retrying next interval: {e}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
