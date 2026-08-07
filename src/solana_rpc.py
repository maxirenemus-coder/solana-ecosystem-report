"""Direct Solana mainnet RPC calls -- network performance, epoch, validators, supply.

Public endpoint (api.mainnet-beta.solana.com), no API key. Rate limits apply on
the public endpoint; a self-hosted or paid RPC can be swapped in via
`--rpc-url` without touching this module's logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .http_client import FetchError, safe_post

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


@dataclass
class NetworkPerformance:
    tps: float | None = None
    non_vote_tps: float | None = None
    slot: int | None = None
    block_height: int | None = None
    block_time_utc: str | None = None
    epoch: int | None = None
    epoch_slot_index: int | None = None
    epoch_slots_total: int | None = None
    epoch_progress_pct: float | None = None
    epoch_eta_hours: float | None = None
    avg_slot_time_ms: float | None = None
    transaction_count: int | None = None
    health: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class FeeInfo:
    """Prioritization fees, in micro-lamports per compute unit.

    These are the *priority* fees users bid on top of the base fee, which is
    what actually moves during congestion. A median of zero is the normal,
    uncongested state -- reported as measured rather than massaged.
    """
    median_priority_fee: float | None = None
    mean_priority_fee: float | None = None
    max_priority_fee: float | None = None
    p95_priority_fee: float | None = None
    samples: int = 0
    nonzero_samples: int = 0
    congestion_note: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidatorStatus:
    active_count: int = 0
    delinquent_count: int = 0
    total_active_stake_sol: float = 0.0
    total_delinquent_stake_sol: float = 0.0
    delinquent_stake_pct: float | None = None
    top_validators: list[dict] = field(default_factory=list)
    avg_commission_pct: float | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class SupplyInfo:
    circulating_sol: float | None = None
    non_circulating_sol: float | None = None
    total_sol: float | None = None
    errors: list[str] = field(default_factory=list)


LAMPORTS_PER_SOL = 1_000_000_000


def _rpc(rpc_url: str, method: str, params: list | None = None):
    return safe_post(rpc_url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}, f"solana_rpc.{method}")


def fetch_network_performance(rpc_url: str = DEFAULT_RPC) -> NetworkPerformance:
    perf = NetworkPerformance()
    try:
        epoch = _rpc(rpc_url, "getEpochInfo")["result"]
        perf.slot = epoch["absoluteSlot"]
        perf.block_height = epoch["blockHeight"]
        perf.epoch = epoch["epoch"]
        perf.epoch_slot_index = epoch["slotIndex"]
        perf.epoch_slots_total = epoch["slotsInEpoch"]
        perf.epoch_progress_pct = round(100 * epoch["slotIndex"] / epoch["slotsInEpoch"], 3)
        perf.transaction_count = epoch.get("transactionCount")
    except (FetchError, KeyError) as e:
        perf.errors.append(f"getEpochInfo: {e}")

    # Average several samples rather than one: a single 60-second window is
    # noisy enough that consecutive runs can differ by hundreds of TPS.
    try:
        samples = _rpc(rpc_url, "getRecentPerformanceSamples", [10])["result"]
        total_tx = sum(s["numTransactions"] for s in samples)
        total_nonvote = sum(s.get("numNonVoteTransactions") or 0 for s in samples)
        total_secs = sum(s["samplePeriodSecs"] for s in samples)
        total_slots = sum(s["numSlots"] for s in samples)
        if total_secs > 0:
            perf.tps = round(total_tx / total_secs, 1)
            perf.non_vote_tps = round(total_nonvote / total_secs, 1)
        if total_slots > 0:
            perf.avg_slot_time_ms = round(1000 * total_secs / total_slots, 1)
            if perf.epoch_slots_total and perf.epoch_slot_index is not None:
                remaining = perf.epoch_slots_total - perf.epoch_slot_index
                perf.epoch_eta_hours = round(remaining * (total_secs / total_slots) / 3600, 1)
    except (FetchError, KeyError, ZeroDivisionError) as e:
        perf.errors.append(f"getRecentPerformanceSamples: {e}")

    if perf.slot:
        try:
            bt = _rpc(rpc_url, "getBlockTime", [perf.block_height or perf.slot]).get("result")
            if isinstance(bt, int):
                from datetime import datetime, timezone
                perf.block_time_utc = datetime.fromtimestamp(bt, timezone.utc).isoformat(timespec="seconds")
        except (FetchError, KeyError) as e:
            perf.errors.append(f"getBlockTime: {e}")

    perf.health = fetch_health(rpc_url)
    return perf


def fetch_fees(rpc_url: str = DEFAULT_RPC) -> FeeInfo:
    """Median and tail prioritization fees across the RPC's recent sample set."""
    import statistics

    fi = FeeInfo()
    try:
        result = _rpc(rpc_url, "getRecentPrioritizationFees")["result"]
        fees = [float(x["prioritizationFee"]) for x in result]
        fi.samples = len(fees)
        if fees:
            fi.nonzero_samples = sum(1 for f in fees if f > 0)
            fi.median_priority_fee = round(statistics.median(fees), 2)
            fi.mean_priority_fee = round(statistics.fmean(fees), 2)
            fi.max_priority_fee = round(max(fees), 2)
            ordered = sorted(fees)
            fi.p95_priority_fee = round(ordered[min(int(len(ordered) * 0.95), len(ordered) - 1)], 2)

            share = fi.nonzero_samples / len(fees)
            if share == 0:
                fi.congestion_note = "No priority fees paid in the sampled slots -- network uncongested."
            elif share < 0.25:
                fi.congestion_note = f"Priority fees present in {share:.0%} of sampled slots -- light contention."
            else:
                fi.congestion_note = f"Priority fees present in {share:.0%} of sampled slots -- active contention for blockspace."
    except (FetchError, KeyError, TypeError, ValueError) as e:
        fi.errors.append(f"getRecentPrioritizationFees: {e}")
    return fi


def fetch_validator_status(rpc_url: str = DEFAULT_RPC, top_n: int = 10) -> ValidatorStatus:
    vs = ValidatorStatus()
    try:
        result = _rpc(rpc_url, "getVoteAccounts")["result"]
        current = result.get("current", [])
        delinquent = result.get("delinquent", [])

        vs.active_count = len(current)
        vs.delinquent_count = len(delinquent)
        vs.total_active_stake_sol = round(sum(v["activatedStake"] for v in current) / LAMPORTS_PER_SOL, 2)
        vs.total_delinquent_stake_sol = round(sum(v["activatedStake"] for v in delinquent) / LAMPORTS_PER_SOL, 2)

        total_stake = vs.total_active_stake_sol + vs.total_delinquent_stake_sol
        if total_stake > 0:
            vs.delinquent_stake_pct = round(100 * vs.total_delinquent_stake_sol / total_stake, 3)

        if current:
            vs.avg_commission_pct = round(sum(v["commission"] for v in current) / len(current), 2)

        top = sorted(current, key=lambda v: v["activatedStake"], reverse=True)[:top_n]
        vs.top_validators = [
            {
                "votePubkey": v["votePubkey"],
                "stake_sol": round(v["activatedStake"] / LAMPORTS_PER_SOL, 2),
                "commission_pct": v["commission"],
            }
            for v in top
        ]
    except (FetchError, KeyError) as e:
        vs.errors.append(f"getVoteAccounts: {e}")

    return vs


def fetch_supply(rpc_url: str = DEFAULT_RPC) -> SupplyInfo:
    si = SupplyInfo()
    try:
        value = _rpc(rpc_url, "getSupply")["result"]["value"]
        si.circulating_sol = round(value["circulating"] / LAMPORTS_PER_SOL, 2)
        si.non_circulating_sol = round(value["nonCirculating"] / LAMPORTS_PER_SOL, 2)
        si.total_sol = round(si.circulating_sol + si.non_circulating_sol, 2)
    except (FetchError, KeyError) as e:
        si.errors.append(f"getSupply: {e}")
    return si


def fetch_health(rpc_url: str = DEFAULT_RPC) -> str:
    try:
        return _rpc(rpc_url, "getHealth")["result"]
    except FetchError as e:
        return f"unreachable: {e}"
