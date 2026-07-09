from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("slack")


def test_champion_mentions_become_signals() -> None:
    from fabric import registry
    from fabric.schema import Signal

    connector = registry.get("slack")
    signals = [
        e
        for raw in connector.pull(since=None)
        for e in connector.normalize(raw)
        if isinstance(e, Signal)
    ]
    assert signals and all(s.kind == "champion_mention" for s in signals)
