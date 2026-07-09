"""Orchestrator: run Network and Conquest in parallel, feed both plus the
Allocator into a synthesis producing the Unified Battle Plan, emitting bus
events throughout."""

from __future__ import annotations

import asyncio

from agents import mock_agents
from agents import schemas as S
from agents import tools as T
from agents.bus import EventBus
from agents.client import llm_available, run_agent_loop


async def _network(target: str, bus: EventBus) -> S.NetworkReport:
    if not llm_available():
        return mock_agents.mock_network(target, bus)
    bus.moved_to("Network", "org-map")
    report = await run_agent_loop(
        "Network",
        "network.md",
        f"Map the relationship fabric around {target}.",
        T.NETWORK_TOOLS,
        "network_report",
        S.NetworkReport,
        bus,
    )
    return report  # type: ignore[return-value]


async def _conquest(target: str, objective: str, bus: EventBus) -> S.ConquestReport:
    if not llm_available():
        return mock_agents.mock_conquest(target, objective, bus)
    bus.moved_to("Conquest", "fortress")
    report = await run_agent_loop(
        "Conquest",
        "conquest.md",
        f"Plan the conquest of {target}; objective: reach the {objective}.",
        T.CONQUEST_TOOLS,
        "conquest_report",
        S.ConquestReport,
        bus,
    )
    return report  # type: ignore[return-value]


async def _relationship(bus: EventBus) -> S.RelationshipReport:
    if not llm_available():
        return mock_agents.mock_relationship(bus)
    bus.moved_to("Relationship", "portfolio")
    report = await run_agent_loop(
        "Relationship",
        "relationship.md",
        "Rank retention risks across the customer portfolio.",
        T.RELATIONSHIP_TOOLS,
        "relationship_report",
        S.RelationshipReport,
        bus,
    )
    return report  # type: ignore[return-value]


def _synthesize(
    network: S.NetworkReport,
    conquest: S.ConquestReport,
    relationship: S.RelationshipReport,
    allocation: dict,
) -> S.BattlePlan:
    """Deterministic synthesis. Live mode could route this through Sonnet, but
    the plan is assembled from structured agent outputs either way."""
    first_hop = conquest.primary_play.steps[0].to_person if conquest.primary_play.steps else "?"
    next_steps = [
        f"Ask for the intro to {first_hop} today"
        + (f" (timing: {conquest.primary_play.timing_signal})"
           if conquest.primary_play.timing_signal else ""),
        f"Run this week's allocation: {len(allocation['plan'])} actions, "
        f"{allocation['budget']['hours_used']}h, shadow price EUR "
        f"{allocation['shadow_price_eur_per_hour']}/h",
    ]
    if relationship.risks:
        top = relationship.risks[0]
        next_steps.append(f"Fire drill on {top.account}: {top.risk}")
    return S.BattlePlan(
        executive_summary=(
            f"Conquest of {conquest.target}: {conquest.summary} "
            f"Network: {network.summary} Portfolio: {relationship.summary}"
        ),
        conquest=conquest,
        network=network,
        allocation=allocation["plan"],
        retention_risks=relationship.risks,
        next_steps=next_steps,
    )


async def conquer(
    target: str = "novapay.io",
    objective: str = "CRO",
    hours: float = 8.0,
    eur: float = 900.0,
    bus: EventBus | None = None,
) -> S.BattlePlan:
    """Full run: Network + Conquest in parallel, Relationship, Allocator,
    synthesis into the Unified Battle Plan."""
    bus = bus or EventBus()
    network_task = asyncio.create_task(_network(target, bus))
    conquest_task = asyncio.create_task(_conquest(target, objective, bus))
    network, conquest = await asyncio.gather(network_task, conquest_task)
    bus.shares_with("Network", "Conquest", f"warm nodes: "
                    f"{', '.join(n.name for n in network.warm_nodes[:3])}")
    relationship = await _relationship(bus)
    bus.moved_to("Allocator", "war-table")
    allocation = T.allocator_solve(hours, eur)
    bus.receives("Allocator", f"{len(allocation['plan'])} actions within budget")
    bus.shares_with("Conquest", "Allocator", "battle plan sections ready")
    plan = _synthesize(network, conquest, relationship, allocation)
    bus.emit("Orchestrator", "done", plan="unified_battle_plan")
    return plan


def conquer_sync(**kwargs) -> S.BattlePlan:
    return asyncio.run(conquer(**kwargs))
