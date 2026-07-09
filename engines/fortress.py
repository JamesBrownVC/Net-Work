"""Fortress pathfinder: most reliable intro paths into a target company.

Builds G from people + org_edges (materialized here from FullEnrich org
hints), attaches a virtual source through warm nodes (warmth >= tau), and
returns the top-3 paths via -ln(p) Dijkstra + Yen, ranked by
EV = V_deal * R - effort. fail_edge drops an edge to epsilon and applies a
blast-radius alpha to sibling edges, then re-solves. Every step carries its
p components (no naked scores).
"""

from __future__ import annotations

import json
import math
from typing import Any

import networkx as nx
import yaml
from sqlalchemy.orm import Session

from engines import warmth as warmth_engine
from fabric.protocol import REPO_ROOT
from fabric.store import OrgEdgeRow, PersonRow, SignalRow, WarmthRow, get_engine

VIRTUAL_SOURCE = "person:__us__"
SENIORITY_RANK = {"IC": 0, "MGR": 1, "DIR": 2, "VP": 3, "C": 4}


def _config() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "config" / "fortress.yaml").read_text(encoding="utf-8"))


def _edge_p(
    rel_type: str, src: PersonRow, dst: PersonRow, cfg: dict[str, Any]
) -> tuple[float, dict[str, Any]]:
    base = float(cfg["base_p"][rel_type])
    gap = abs(
        SENIORITY_RANK.get(src.seniority_level, 0) - SENIORITY_RANK.get(dst.seniority_level, 0)
    )
    gap_term = 1.0 - float(cfg["seniority_gap_penalty"]) * gap
    dept_term = (
        float(cfg["dept_factor_same"]) if src.dept == dst.dept
        else float(cfg["dept_factor_cross"])
    )
    p = max(float(cfg["p_min"]), min(float(cfg["p_max"]), base * gap_term * dept_term))
    return p, {
        "rel_type": rel_type,
        "base_p": base,
        "seniority_gap": gap,
        "gap_term": round(gap_term, 3),
        "dept_term": dept_term,
        "p": round(p, 4),
    }


def build_org_edges(session: Session, company_domain: str) -> int:
    """Materialize org_edges from the FullEnrich org_structure signal:
    manages, peer (same manager), skip (manager's manager), cross_dept heads."""
    cfg = _config()
    cid = f"company:{company_domain.lower()}"
    signal = (
        session.query(SignalRow)
        .filter(SignalRow.company_id == cid, SignalRow.kind == "org_structure")
        .first()
    )
    if signal is None:
        return 0
    lines = json.loads(signal.payload_json)["reporting_lines"]
    people = {p.email: p for p in session.query(PersonRow).filter(PersonRow.company_id == cid)}
    manager_of = {r["person"]: r["manager"] for r in lines if r["manager"]}

    def add(src: PersonRow, dst: PersonRow, rel: str) -> None:
        p, comp = _edge_p(rel, src, dst, cfg)
        session.merge(
            OrgEdgeRow(
                src_person=src.id,
                dst_person=dst.id,
                rel_type=rel,
                p_uv=p,
                p_components_json=json.dumps(comp, sort_keys=True),
            )
        )

    n = 0
    for email, mgr_email in manager_of.items():
        person, mgr = people.get(email), people.get(mgr_email)
        if not person or not mgr:
            continue
        add(person, mgr, "manages")
        add(mgr, person, "manages")
        n += 2
        skip_email = manager_of.get(mgr_email)
        if skip_email and skip_email in people:
            add(person, people[skip_email], "skip")
            n += 1
    by_manager: dict[str, list[str]] = {}
    for email, mgr_email in manager_of.items():
        by_manager.setdefault(mgr_email, []).append(email)
    for siblings in by_manager.values():
        for i, a in enumerate(siblings):
            for b in siblings[i + 1 :]:
                if a in people and b in people:
                    add(people[a], people[b], "peer")
                    add(people[b], people[a], "peer")
                    n += 2
    heads = [p for p in people.values() if p.seniority_level in ("VP", "C", "DIR")]
    for i, a in enumerate(heads):
        for b in heads[i + 1 :]:
            if a.dept != b.dept:
                add(a, b, "cross_dept")
                add(b, a, "cross_dept")
                n += 2
    session.commit()
    return n


def build_graph(session: Session, company_domain: str) -> nx.DiGraph:
    cfg = _config()
    cid = f"company:{company_domain.lower()}"
    if (
        session.query(OrgEdgeRow)
        .join(PersonRow, PersonRow.id == OrgEdgeRow.src_person)
        .filter(PersonRow.company_id == cid)
        .count()
        == 0
    ):
        build_org_edges(session, company_domain)
    warmth_engine.compute_all(session, company_domain)
    g = nx.DiGraph()
    people = {p.id: p for p in session.query(PersonRow).filter(PersonRow.company_id == cid)}
    for pid, person in people.items():
        g.add_node(pid, name=person.full_name, title=person.title, dept=person.dept)
    g.add_node(VIRTUAL_SOURCE, name="Atlas (us)", title="virtual source", dept="-")
    for edge in session.query(OrgEdgeRow).all():
        if edge.src_person in people and edge.dst_person in people:
            g.add_edge(
                edge.src_person,
                edge.dst_person,
                p=edge.p_uv,
                components=json.loads(edge.p_components_json),
            )
    tau = float(cfg["warm_tau"])
    for pid in people:
        w = session.get(WarmthRow, pid)
        if w and w.score >= tau:
            g.add_edge(
                VIRTUAL_SOURCE,
                pid,
                p=w.score,
                components={"rel_type": "external_mutual", "warmth": w.score,
                            "warmth_components": json.loads(w.components_json)},
            )
    return g


def _find_target(session: Session, company_domain: str, target: str) -> PersonRow:
    cid = f"company:{company_domain.lower()}"
    query = session.query(PersonRow).filter(PersonRow.company_id == cid)
    exact = query.filter(PersonRow.title.ilike(target)).first()
    if exact:
        return exact
    fuzzy = query.filter(PersonRow.title.ilike(f"%{target}%")).first()
    if fuzzy:
        return fuzzy
    raise ValueError(f"no person matching title {target!r} at {company_domain}")


def _paths_payload(
    g: nx.DiGraph, target_id: str, v_deal: float, cfg: dict[str, Any], k: int = 3
) -> list[dict[str, Any]]:
    for _u, _v, data in g.edges(data=True):
        data["nlp"] = -math.log(max(data["p"], 1e-9))
    try:
        gen = nx.shortest_simple_paths(g, VIRTUAL_SOURCE, target_id, weight="nlp")
        raw_paths = []
        for i, path in enumerate(gen):
            raw_paths.append(path)
            if i + 1 >= k:
                break
    except nx.NetworkXNoPath:
        return []
    effort_per_hop = float(cfg["effort_per_hop"])
    out = []
    for path in raw_paths:
        steps = []
        r = 1.0
        for u, v in zip(path, path[1:], strict=False):
            data = g.edges[u, v]
            r *= data["p"]
            steps.append(
                {
                    "from": g.nodes[u]["name"],
                    "to": g.nodes[v]["name"],
                    "to_title": g.nodes[v]["title"],
                    "p": round(data["p"], 4),
                    "p_components": data["components"],
                }
            )
        effort = effort_per_hop * len(steps)
        out.append(
            {
                "steps": steps,
                "R": round(r, 4),
                "effort": effort,
                "EV": round(v_deal * r - effort, 2),
            }
        )
    out.sort(key=lambda p: p["EV"], reverse=True)
    return out


def solve(
    company_domain: str,
    target: str,
    v_deal: float = 50_000.0,
    session: Session | None = None,
    graph: nx.DiGraph | None = None,
) -> dict[str, Any]:
    """Top-3 most reliable intro paths to a target person (by title match)."""
    own = session is None
    if own:
        session = Session(get_engine())
    try:
        person = _find_target(session, company_domain, target)
        g = graph if graph is not None else build_graph(session, company_domain)
        return {
            "target": {"name": person.full_name, "title": person.title},
            "v_deal": v_deal,
            "paths": _paths_payload(g, person.id, v_deal, _config()),
        }
    finally:
        if own:
            session.close()


def fail_edge(
    company_domain: str,
    target: str,
    from_person: str,
    to_person: str,
    v_deal: float = 50_000.0,
    session: Session | None = None,
) -> dict[str, Any]:
    """Mark an intro as failed (p -> epsilon), damp sibling edges by alpha,
    and re-solve. Person args match on full name or person id."""
    cfg = _config()
    own = session is None
    if own:
        session = Session(get_engine())
    try:
        g = build_graph(session, company_domain)

        def resolve(label: str) -> str:
            if label in g:
                return label
            if label == "us":
                return VIRTUAL_SOURCE
            for node, data in g.nodes(data=True):
                if data.get("name", "").lower() == label.lower():
                    return node
            raise ValueError(f"unknown person {label!r}")

        u, v = resolve(from_person), resolve(to_person)
        eps, alpha = float(cfg["epsilon_failed"]), float(cfg["blast_radius_alpha"])
        if not g.has_edge(u, v):
            raise ValueError(f"no edge {from_person} -> {to_person}")
        g.edges[u, v]["p"] = eps
        g.edges[u, v]["components"]["failed"] = True
        for _, sib, data in g.out_edges(u, data=True):
            if sib != v:
                data["p"] = max(eps, data["p"] * alpha)
                data["components"]["blast_radius_damped"] = alpha
        result = solve(company_domain, target, v_deal, session=session, graph=g)
        result["failed_edge"] = {"from": from_person, "to": to_person, "p": eps}
        return result
    finally:
        if own:
            session.close()
