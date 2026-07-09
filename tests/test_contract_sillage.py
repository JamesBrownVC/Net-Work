from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("sillage")


def test_scripted_story_signals() -> None:
    from fabric import registry

    connector = registry.get("sillage")
    novapay = connector.signals_for("novapay.io")
    kinds = {s["kind"] for s in novapay}
    assert {"champion_move", "hiring_spike", "buying_intent"} <= kinds
    for raw in connector.pull(since=None):
        for entity in connector.normalize(raw):
            assert 0.0 <= entity.strength <= 1.0
