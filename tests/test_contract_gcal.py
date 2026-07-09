from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("gcal")


def test_upcoming_call_slots() -> None:
    from fabric import registry

    connector = registry.get("gcal")
    upcoming = connector.upcoming(days=7)
    calls = [e for e in upcoming if e.get("is_call_slot")]
    assert calls, "expected upcoming call slots for the calendar"
    # each carries a person and a purpose, and lands within the horizon
    for c in calls:
        assert c.get("person_email") and c.get("purpose")
    # at least one call is scheduled tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    assert any(datetime.fromisoformat(c["ts"]).date() == tomorrow for c in calls)
