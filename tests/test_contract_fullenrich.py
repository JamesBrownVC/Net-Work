from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("fullenrich")


def test_enrich_company_novapay() -> None:
    from fabric import registry

    connector = registry.get("fullenrich")
    block = connector.enrich_company("novapay.io")
    assert len(block["people"]) == 35
    assert len(block["warm_nodes"]) == 4
    depts = {p["dept"] for p in block["people"]}
    assert {"Sales", "Finance", "Engineering", "Ops"} <= depts
    managed = [p for p in block["people"] if p["manager_email"]]
    assert len(managed) == 34  # everyone but the CEO


def test_lookalikes() -> None:
    from fabric import registry

    out = registry.get("fullenrich").lookalikes(["novapay.io"], n=3)
    assert len(out) == 3
