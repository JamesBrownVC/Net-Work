from __future__ import annotations

from datetime import datetime, timedelta

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("gcal")


def test_meeting_tomorrow() -> None:
    from fabric import registry

    connector = registry.get("gcal")
    upcoming = connector.upcoming(days=2)
    assert any(e["id"] == "gcal:tomorrow" for e in upcoming)
    tomorrow = next(e for e in upcoming if e["id"] == "gcal:tomorrow")
    ts = datetime.fromisoformat(tomorrow["ts"])
    assert ts.date() == (datetime.now() + timedelta(days=1)).date()
