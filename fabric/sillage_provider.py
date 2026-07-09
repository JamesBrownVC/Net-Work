"""Sillage signal provider: live-with-cached-fallback.

Per the user's instruction, always prefer the live Sillage API and fall back to
cached data when it is unavailable. The 13 insurer accounts and their cached
signals come from the feature/sillage-signals branch. The live endpoint shape
lives in config/apis.yaml (verified: false) and any failure - no key, network,
unverified endpoint - transparently degrades to the cached fixture.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

import yaml

from fabric.protocol import FIXTURES_DIR, REPO_ROOT

_SILLAGE_DIR = FIXTURES_DIR / "sillage"


@lru_cache(maxsize=1)
def insurer_accounts() -> list[dict[str, Any]]:
    data = json.loads((_SILLAGE_DIR / "insurers.json").read_text(encoding="utf-8"))
    return data["accounts"]


@lru_cache(maxsize=1)
def _cached_signals() -> dict[str, list[dict[str, Any]]]:
    data = json.loads((_SILLAGE_DIR / "insurer_signals.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _sillage_base() -> str:
    cfg = yaml.safe_load((REPO_ROOT / "config" / "apis.yaml").read_text(encoding="utf-8"))
    return cfg["sillage"]["base_url"]


def _fetch_live(domain: str) -> list[dict[str, Any]] | None:
    """Attempt the live Sillage V2 signals call. Returns None on any failure so
    the caller falls back to cache. Endpoint is unverified (config/apis.yaml),
    so this is best-effort and never raises."""
    key = os.getenv("SILLAGE_API_KEY")
    if not key or os.getenv("MOCK_MODE", "true").strip().lower() != "false":
        return None
    try:
        import httpx

        resp = httpx.get(
            f"{_sillage_base()}/signals",
            params={"domain": domain},
            headers={"Authorization": f"Bearer {key}"},
            timeout=6.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("signals", payload) if isinstance(payload, dict) else payload
    except Exception:
        return None


def signals_for(domain: str) -> dict[str, Any]:
    """Signals for an insurer domain. {source: live|cached|none, signals: [...]}."""
    live = _fetch_live(domain)
    if live is not None:
        return {"source": "live", "signals": live}
    cached = _cached_signals().get(domain.lower())
    if cached is not None:
        return {"source": "cached", "signals": cached}
    return {"source": "none", "signals": []}


def is_insurer(domain: str) -> bool:
    return any(a["domain"] == domain.lower() for a in insurer_accounts())


def account_meta(domain: str) -> dict[str, Any] | None:
    for a in insurer_accounts():
        if a["domain"] == domain.lower():
            return a
    return None
