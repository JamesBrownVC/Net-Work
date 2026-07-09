from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("gmail")


def test_whale_silent_72_days() -> None:
    from fabric import registry

    records = registry.get("gmail").pull(since=None)
    cutoff = datetime.now() - timedelta(days=70)
    recent_whale = [
        r for r in records
        if r.payload["company_domain"] == "meridianbank.example"
        and datetime.fromisoformat(r.payload["ts"]) > cutoff
    ]
    assert recent_whale == []


def test_reply_latency_present_on_inbound() -> None:
    from fabric import registry

    records = registry.get("gmail").pull(since=None)
    inbound = [r for r in records if r.payload["direction"] == "inbound"]
    assert inbound and all(r.payload["latency_hours"] is not None for r in inbound)
