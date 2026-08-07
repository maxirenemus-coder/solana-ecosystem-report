"""Minimal HTTP client using only the Python standard library.

No `requests`, no third-party packages. The bounty brief explicitly prefers
solutions with "no API keys or external dependencies beyond Python stdlib and
Solana blockchain for direct RPC calls" -- this module is what makes that true
end to end: `pip install` is never required to run this report.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "solana-ecosystem-report/0.1 (stdlib-only)"
TIMEOUT = 20


def get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


class FetchError(RuntimeError):
    """Raised when a data source is unreachable or returns something unusable.

    Every fetcher catches its own errors and reports them per-source instead of
    letting one dead endpoint take down the whole report -- a stale price feed
    should not hide that validator data still loaded fine.
    """

    def __init__(self, source: str, detail: str):
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail


def safe_get(url: str, source: str) -> Any:
    try:
        return get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        raise FetchError(source, str(e)) from e


def safe_post(url: str, payload: dict, source: str) -> Any:
    try:
        return post_json(url, payload)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        raise FetchError(source, str(e)) from e
