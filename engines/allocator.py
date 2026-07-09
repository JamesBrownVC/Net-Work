"""MCKP allocator: pick at most one action per account to maximize expected
euro uplift under rep-hours and euro budgets.

Solved with OR-Tools CP-SAT; the LP relaxation (GLOP) reports the dual of the
hours constraint as shadow_price_eur_per_hour. A greedy fallback sits behind
a flag. `claude_adjustment` is a Phase 3 stub: bounded +/- 40 percent,
evidence-citing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yaml
from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from engines import warmth as warmth_engine
from fabric.protocol import REPO_ROOT
from fabric.store import CompanyRow, PersonRow, WarmthRow

SCALE = 100  # CP-SAT works on integers; euros scaled to cents of expected value


@dataclass
class Candidate:
    account: str
    domain: str
    action: str
    hours: float
    eur_cost: float
    delta_p: float
    value_eur: float

    @property
    def u_eur(self) -> float:
        return self.delta_p * self.value_eur

    def components(self) -> dict[str, Any]:
        return {
            "delta_p": self.delta_p,
            "value_eur": self.value_eur,
            "hours": self.hours,
            "eur_cost": self.eur_cost,
            "u_eur": round(self.u_eur, 2),
        }


def _load_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "config" / name).read_text(encoding="utf-8"))


def _bucket(value: float, edges: dict[str, float], names: tuple[str, str, str]) -> str:
    lo, hi = names[0], names[2]
    keys = list(edges.values())
    if value < keys[0]:
        return lo
    if value < keys[1]:
        return names[1]
    return hi


def account_warmth(session: Session, company: CompanyRow) -> float:
    """Max contact warmth at the account (the strongest thread we hold)."""
    scores = [
        w.score
        for _, w in session.query(PersonRow, WarmthRow)
        .join(WarmthRow, WarmthRow.person_id == PersonRow.id)
        .filter(PersonRow.company_id == company.id)
        .all()
    ]
    return max(scores, default=0.0)


def build_candidates(session: Session) -> list[Candidate]:
    actions = _load_yaml("actions.yaml")["actions"]
    up = _load_yaml("uplifts.yaml")
    warmth_engine.compute_all(session)
    candidates: list[Candidate] = []
    for company in session.query(CompanyRow).filter(CompanyRow.is_customer.is_(True)).all():
        w = account_warmth(session, company)
        wb = _bucket(w, up["buckets"]["warmth"], ("cold", "warm", "hot"))
        vt = _bucket(company.arr, up["buckets"]["value_eur"], ("low", "mid", "high"))
        for action, cost in actions.items():
            delta = up["uplifts"].get(action, {}).get(wb, {}).get(vt, up["default"])
            candidates.append(
                Candidate(
                    account=company.name,
                    domain=company.domain,
                    action=action,
                    hours=float(cost["hours"]),
                    eur_cost=float(cost["eur"]),
                    delta_p=float(delta),
                    value_eur=company.arr,
                )
            )
    return candidates


def solve_cpsat(
    candidates: list[Candidate], hours_budget: float, eur_budget: float
) -> list[Candidate]:
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{i}") for i in range(len(candidates))]
    by_account: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        by_account.setdefault(c.domain, []).append(i)
    for idxs in by_account.values():
        model.add(sum(x[i] for i in idxs) <= 1)
    model.add(
        sum(int(c.hours * SCALE) * x[i] for i, c in enumerate(candidates))
        <= int(hours_budget * SCALE)
    )
    model.add(
        sum(int(c.eur_cost * SCALE) * x[i] for i, c in enumerate(candidates))
        <= int(eur_budget * SCALE)
    )
    model.maximize(sum(int(c.u_eur * SCALE) * x[i] for i, c in enumerate(candidates)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT failed with status {status}")
    return [c for i, c in enumerate(candidates) if solver.value(x[i])]


def shadow_price(
    candidates: list[Candidate], hours_budget: float, eur_budget: float
) -> float:
    """Dual of the hours constraint from the LP relaxation (GLOP)."""
    solver = pywraplp.Solver.CreateSolver("GLOP")
    x = [solver.NumVar(0.0, 1.0, f"x{i}") for i in range(len(candidates))]
    by_account: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        by_account.setdefault(c.domain, []).append(i)
    for idxs in by_account.values():
        solver.Add(sum(x[i] for i in idxs) <= 1)
    hours_ct = solver.Add(
        sum(c.hours * x[i] for i, c in enumerate(candidates)) <= hours_budget
    )
    solver.Add(sum(c.eur_cost * x[i] for i, c in enumerate(candidates)) <= eur_budget)
    solver.Maximize(sum(c.u_eur * x[i] for i, c in enumerate(candidates)))
    if solver.Solve() != pywraplp.Solver.OPTIMAL:
        return 0.0
    return round(hours_ct.dual_value(), 2)


def solve_greedy(
    candidates: list[Candidate], hours_budget: float, eur_budget: float
) -> list[Candidate]:
    """Fallback: best U per hour first, one action per account."""
    chosen: list[Candidate] = []
    taken: set[str] = set()
    hours = eur = 0.0
    ranked = sorted(
        (c for c in candidates if c.u_eur > 0),
        key=lambda c: c.u_eur / max(c.hours, 0.1),
        reverse=True,
    )
    for c in ranked:
        if c.domain in taken or hours + c.hours > hours_budget or eur + c.eur_cost > eur_budget:
            continue
        chosen.append(c)
        taken.add(c.domain)
        hours += c.hours
        eur += c.eur_cost
    return chosen


ADJUSTMENT_BOUND = 0.40  # Claude may shift delta_p by at most +/- 40 percent


def apply_adjustments(
    candidates: list[Candidate], adjustments: dict[str, dict[str, Any]]
) -> list[Candidate]:
    """Apply {domain: {factor, citations}} adjustments. Factors are clamped to
    +/- ADJUSTMENT_BOUND and entries without citations are rejected."""
    for c in candidates:
        adj = adjustments.get(c.domain)
        if not adj or not adj.get("citations"):
            continue
        factor = max(-ADJUSTMENT_BOUND, min(ADJUSTMENT_BOUND, float(adj["factor"])))
        c.delta_p = round(c.delta_p * (1.0 + factor), 5)
    return candidates


def claude_adjustment(
    session: Session, candidates: list[Candidate]
) -> list[Candidate]:
    """Claude (Sonnet) reads each account's last 5 interactions + signals and
    returns bounded uplift adjustments with cited row ids. Without an API key
    this is the identity so the allocator stays fully mock-runnable."""
    import os

    if not os.getenv("ANTHROPIC_API_KEY"):
        return candidates
    import asyncio

    from agents import tools as agent_tools
    from agents.client import extract
    from engines.adjustment_schema import AccountAdjustment

    domains = sorted({c.domain for c in candidates})
    adjustments: dict[str, dict[str, Any]] = {}

    async def one(domain: str) -> None:
        context = agent_tools.recent_context(domain, n=5)
        prompt = (
            f"Account {domain}. Recent interactions, signals, and content analysis "
            f"(sentiment/champions/risks):\n{json.dumps(context)}\n"
            "Weigh the content_analysis substance (sentiment trend, risk flags, "
            "champion signals), not just the metadata. Return an uplift adjustment "
            "factor in [-0.4, 0.4] for this account's action uplifts and cite the "
            "interaction/signal ids justifying it. Return factor 0 with empty "
            "citations if nothing is noteworthy."
        )
        result = await extract(prompt, AccountAdjustment)
        if result.citations:
            adjustments[domain] = {"factor": result.factor, "citations": result.citations}

    async def run() -> None:
        await asyncio.gather(*(one(d) for d in domains))

    asyncio.run(run())
    return apply_adjustments(candidates, adjustments)


def solve(
    hours_budget: float,
    eur_budget: float,
    greedy: bool = False,
    session: Session | None = None,
) -> dict[str, Any]:
    """Full allocation: plan items with components, budget usage, shadow price."""
    from fabric.store import get_engine

    own_session = session is None
    if own_session:
        session = Session(get_engine())
    try:
        candidates = claude_adjustment(session, build_candidates(session))
        picked = (
            solve_greedy(candidates, hours_budget, eur_budget)
            if greedy
            else solve_cpsat(candidates, hours_budget, eur_budget)
        )
        picked.sort(key=lambda c: c.u_eur, reverse=True)
        return {
            "plan": [
                {
                    "account": c.account,
                    "action": c.action,
                    "U_eur": round(c.u_eur, 2),
                    "components": c.components(),
                }
                for c in picked
            ],
            "budget": {
                "hours_used": round(sum(c.hours for c in picked), 1),
                "hours_budget": hours_budget,
                "eur_used": round(sum(c.eur_cost for c in picked), 2),
                "eur_budget": eur_budget,
            },
            "shadow_price_eur_per_hour": shadow_price(candidates, hours_budget, eur_budget),
            "solver": "greedy" if greedy else "cp_sat",
        }
    finally:
        if own_session:
            session.close()


def solve_json(hours_budget: float, eur_budget: float, greedy: bool = False) -> str:
    return json.dumps(solve(hours_budget, eur_budget, greedy), indent=1)
