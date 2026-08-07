"""Snapshot persistence -- what makes this "auto-updating" rather than "re-runnable".

Each run appends a compact record to a JSONL file. Two things become possible
that a single stateless run cannot do:

1. **Network activity between runs.** `getEpochInfo.transactionCount` is a
   cumulative counter. One reading is meaningless; two readings and their
   timestamps give real transactions-per-second and a projected daily volume,
   measured rather than sampled from a 60-second window.

2. **Metrics with no public history feed** (validator counts, delinquency)
   accumulate their own history here, so anomaly detection on them improves
   the longer the report runs, instead of staying frozen on assumptions.

JSONL is used deliberately: appending is atomic-ish per line, a corrupted
write costs one record instead of the whole history, and the file stays
greppable without a database.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAX_RECORDS = 5000  # roughly 3 years of hourly runs; keeps the file small


@dataclass
class ActivityDelta:
    """Network throughput measured between two runs, not sampled."""
    transactions: int | None = None
    seconds_elapsed: float | None = None
    tps_measured: float | None = None
    projected_daily_transactions: int | None = None
    slots_elapsed: int | None = None
    basis: str = ""


def _record_from(snapshot: dict) -> dict:
    perf = snapshot.get("network_performance", {})
    val = snapshot.get("validator_status", {})
    price = snapshot.get("price", {})
    growth = snapshot.get("ecosystem_growth", {})
    return {
        "ts": snapshot.get("generated_at"),
        "slot": perf.get("slot"),
        "transaction_count": perf.get("transaction_count"),
        "tps_sampled": perf.get("tps"),
        "epoch": perf.get("epoch"),
        "active_validators": val.get("active_count"),
        "delinquent_validators": val.get("delinquent_count"),
        "delinquent_stake_pct": val.get("delinquent_stake_pct"),
        "price_usd": price.get("usd"),
        "tvl_usd": growth.get("tvl_usd"),
    }


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # one bad line never invalidates the rest
    return out


def append(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = _record_from(snapshot)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    records = load(path)
    if len(records) > MAX_RECORDS:
        trimmed = records[-MAX_RECORDS:]
        path.write_text("\n".join(json.dumps(r) for r in trimmed) + "\n", encoding="utf-8")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_activity(history: list[dict], current: dict) -> ActivityDelta:
    """Measure throughput between the newest prior snapshot and this one."""
    d = ActivityDelta()
    perf = current.get("network_performance", {})
    tx_now = perf.get("transaction_count")
    slot_now = perf.get("slot")
    ts_now = _parse_ts(current.get("generated_at"))

    if tx_now is None or ts_now is None:
        d.basis = "no prior snapshot with a transaction counter yet -- run again to measure"
        return d

    prior = None
    for rec in reversed(history):
        if rec.get("transaction_count") and _parse_ts(rec.get("ts")):
            prior = rec
            break

    if prior is None:
        d.basis = "first run: throughput between runs becomes available on the next run"
        return d

    ts_prev = _parse_ts(prior["ts"])
    elapsed = (ts_now - ts_prev).total_seconds()
    if elapsed <= 0:
        d.basis = "prior snapshot is not older than this one; skipped"
        return d

    d.transactions = tx_now - prior["transaction_count"]
    d.seconds_elapsed = round(elapsed, 1)
    if d.transactions >= 0:
        d.tps_measured = round(d.transactions / elapsed, 1)
        d.projected_daily_transactions = int(d.tps_measured * 86400)
    if slot_now and prior.get("slot"):
        d.slots_elapsed = slot_now - prior["slot"]
    d.basis = (f"measured across {elapsed / 3600:.2f}h between snapshots "
               f"{prior['ts']} and {current['generated_at']}")
    return d


def build_series(history: list[dict], key: str) -> tuple[list[int], list[float]]:
    """Extract a (timestamps, values) pair from accumulated snapshots."""
    ts, vals = [], []
    for rec in history:
        dt = _parse_ts(rec.get("ts"))
        v = rec.get(key)
        if dt is not None and isinstance(v, (int, float)):
            ts.append(int(dt.timestamp()))
            vals.append(float(v))
    return ts, vals
