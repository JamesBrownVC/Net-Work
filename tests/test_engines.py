from __future__ import annotations

import itertools
import math

import networkx as nx

from engines import allocator, fortress


def _cand(account: str, action: str, u: float, hours: float, eur: float) -> allocator.Candidate:
    # delta_p * value = u exactly, with value 1000 for clean arithmetic
    return allocator.Candidate(
        account=account, domain=account, action=action,
        hours=hours, eur_cost=eur, delta_p=u / 1000.0, value_eur=1000.0,
    )


def test_knapsack_matches_hand_computed_optimum() -> None:
    # Hand check, hours budget 6, no euro pressure:
    #   acct1: A (u=100, 2h) or B (u=120, 8h)  [at most one per account]
    #   acct2: C (u=90, 3h)
    #   acct3: D (u=60, 1h)
    # Feasible bests: {A,C,D} = 6h, u=250. B never fits. Optimum = 250.
    cands = [
        _cand("acct1", "A", 100, 2, 0),
        _cand("acct1", "B", 120, 8, 0),
        _cand("acct2", "C", 90, 3, 0),
        _cand("acct3", "D", 60, 1, 0),
    ]
    picked = allocator.solve_cpsat(cands, hours_budget=6, eur_budget=1000)
    assert {c.action for c in picked} == {"A", "C", "D"}
    assert round(sum(c.u_eur for c in picked), 2) == 250.0


def test_knapsack_euro_constraint_binds() -> None:
    # Same items but C now costs EUR 500 against a 400 budget: C drops out,
    # freeing hours so B (8h) still exceeds 6h. Optimum = {A, D} = 160.
    cands = [
        _cand("acct1", "A", 100, 2, 0),
        _cand("acct1", "B", 120, 8, 0),
        _cand("acct2", "C", 90, 3, 500),
        _cand("acct3", "D", 60, 1, 0),
    ]
    picked = allocator.solve_cpsat(cands, hours_budget=6, eur_budget=400)
    assert {c.action for c in picked} == {"A", "D"}
    assert round(sum(c.u_eur for c in picked), 2) == 160.0


def test_shadow_price_positive_when_hours_bind() -> None:
    cands = [
        _cand("acct1", "A", 100, 2, 0),
        _cand("acct2", "C", 90, 3, 0),
        _cand("acct3", "D", 60, 1, 0),
    ]
    assert allocator.shadow_price(cands, hours_budget=3, eur_budget=1000) > 0
    assert allocator.shadow_price(cands, hours_budget=100, eur_budget=1000) == 0


def _six_node_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    for node in [fortress.VIRTUAL_SOURCE, "a", "b", "c", "d", "t"]:
        g.add_node(node, name=node, title=node, dept="-")
    edges = [
        (fortress.VIRTUAL_SOURCE, "a", 0.9),
        (fortress.VIRTUAL_SOURCE, "b", 0.6),
        ("a", "c", 0.5),
        ("a", "d", 0.8),
        ("b", "t", 0.7),
        ("c", "t", 0.9),
        ("d", "t", 0.6),
    ]
    for u, v, p in edges:
        g.add_edge(u, v, p=p, components={"p": p})
    return g


def test_fortress_most_reliable_path_matches_enumeration() -> None:
    g = _six_node_graph()
    cfg = {"effort_per_hop": 0.0}
    paths = fortress._paths_payload(g, "t", v_deal=1.0, cfg=cfg, k=3)
    # brute force all simple paths, reliability = product of p
    best_r = 0.0
    for path in nx.all_simple_paths(g, fortress.VIRTUAL_SOURCE, "t"):
        r = math.prod(g.edges[u, v]["p"] for u, v in itertools.pairwise(path))
        best_r = max(best_r, r)
    # hand check: S->a->d->t = .9*.8*.6 = .432; S->b->t = .42; S->a->c->t = .405
    assert abs(best_r - 0.432) < 1e-9
    assert abs(paths[0]["R"] - 0.432) < 1e-6
    assert [s["to"] for s in paths[0]["steps"]] == ["a", "d", "t"]
    assert len(paths) == 3


def test_fortress_solve_and_fail_edge_reroutes() -> None:
    result = fortress.solve("novapay.io", "CRO", v_deal=100_000)
    assert result["target"]["title"] == "CRO"
    assert len(result["paths"]) == 3
    for path in result["paths"]:
        assert path["R"] > 0
        for step in path["steps"]:
            assert "p_components" in step and step["p_components"]
    first = result["paths"][0]["steps"][0]
    rerouted = fortress.fail_edge(
        "novapay.io", "CRO", "us", first["to"], v_deal=100_000
    )
    new_first_hops = [p["steps"][0]["to"] for p in rerouted["paths"]]
    assert rerouted["paths"][0]["R"] < result["paths"][0]["R"] or (
        first["to"] not in new_first_hops
    )


def test_allocator_on_seeded_data() -> None:
    result = allocator.solve(8.0, 900.0)
    assert result["plan"], "expected a non-empty plan on seeded data"
    assert result["budget"]["hours_used"] <= 8.0
    assert result["budget"]["eur_used"] <= 900.0
    assert "shadow_price_eur_per_hour" in result
    for item in result["plan"]:
        assert item["U_eur"] > 0
        assert set(item["components"]) >= {"delta_p", "value_eur", "hours", "eur_cost"}
    greedy = allocator.solve(8.0, 900.0, greedy=True)
    opt = sum(i["U_eur"] for i in result["plan"])
    assert sum(i["U_eur"] for i in greedy["plan"]) <= opt + 1e-6


def test_warmth_components_and_bounds() -> None:
    from sqlalchemy.orm import Session

    from engines import warmth as warmth_engine
    from fabric.store import get_engine

    with Session(get_engine()) as session:
        rows = warmth_engine.company_heatmap(session, "novapay.io")
    assert rows
    for r in rows:
        assert 0.0 <= r["warmth"] <= 1.0
        assert set(r["components"]) == {
            "recency_decay", "freq_90d", "reciprocity", "seniority_touch", "channel_diversity",
        }
    # the 4 warm nodes carry gmail history and must outrank cold members
    assert rows[0]["warmth"] > rows[-1]["warmth"]
