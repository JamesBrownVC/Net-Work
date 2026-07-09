from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("notion")


def test_six_case_studies() -> None:
    from fabric import registry
    from fabric.schema import Reference

    connector = registry.get("notion")
    refs = [
        e
        for raw in connector.pull(since=None)
        for e in connector.normalize(raw)
        if isinstance(e, Reference)
    ]
    assert len(refs) == 6
