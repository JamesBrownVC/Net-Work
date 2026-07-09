from __future__ import annotations

from datetime import datetime

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("gcal")


def test_meeting_tomorrow() -> None:
    from fabric import registry

    connector = registry.get("gcal")
    upcoming = connector.upcoming(days=2)
    assert any(e["id"] == "gcal:tomorrow" for e in upcoming)
    tomorrow = next(e for e in upcoming if e["id"] == "gcal:tomorrow")
    delta = datetime.fromisoformat(tomorrow["ts"]) - datetime.now()
    assert 0 < delta.days <= 1 or (delta.days == 1)
