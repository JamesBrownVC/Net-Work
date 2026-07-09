from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("mockcrm")


def test_25_customers_arr_bounds() -> None:
    from fabric import registry
    from fabric.schema import Company

    connector = registry.get("mockcrm")
    companies = [
        e
        for raw in connector.pull(since=None)
        for e in connector.normalize(raw)
        if isinstance(e, Company)
    ]
    assert len(companies) == 25
    assert all(8_000 <= c.arr <= 400_000 for c in companies)
    assert all(c.is_customer for c in companies)
