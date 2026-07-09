from __future__ import annotations

import asyncio


def test_orchestrator_full_run_mock_mode() -> None:
    from agents.bus import EventBus
    from agents.orchestrator import conquer

    bus = EventBus()
    plan = asyncio.run(conquer(target="novapay.io", objective="CRO", bus=bus))
    assert plan.conquest.primary_play.steps
    assert plan.conquest.primary_play.reliability > 0
    assert plan.network.warm_nodes
    assert plan.allocation
    assert plan.next_steps
    md = plan.to_markdown()
    assert "Unified Battle Plan" in md and "Conquest" in md
    # coherent choreography: each agent moved, asked, and received
    kinds_by_agent: dict[str, set[str]] = {}
    for event in bus.log:
        kinds_by_agent.setdefault(event.agent, set()).add(event.kind)
    for agent in ("Network", "Conquest", "Relationship"):
        assert {"moved_to", "asks", "receives"} <= kinds_by_agent[agent], agent
    assert any(e.kind == "shares_with" for e in bus.log)
    assert bus.log[-1].kind == "done"


def test_conquest_report_cites_objections_and_signals() -> None:
    from agents.bus import EventBus
    from agents.mock_agents import mock_conquest

    report = mock_conquest("novapay.io", "CRO", EventBus())
    assert len(report.objections) == 3  # price, timing, security from the fixture call
    assert report.primary_play.timing_signal, "timing must be anchored to a signal"
    assert report.fallback_play is not None


def test_adjustment_bounds_and_citation_rejection() -> None:
    from engines.allocator import Candidate, apply_adjustments

    def cand() -> Candidate:
        return Candidate(
            account="X", domain="x.io", action="a", hours=1, eur_cost=0,
            delta_p=0.10, value_eur=1000,
        )

    # over-bound factor is clamped to +40 percent
    c = apply_adjustments([cand()], {"x.io": {"factor": 2.0, "citations": ["interaction:1"]}})[0]
    assert abs(c.delta_p - 0.14) < 1e-9
    # missing citations -> rejected, delta_p unchanged
    c = apply_adjustments([cand()], {"x.io": {"factor": 0.4, "citations": []}})[0]
    assert c.delta_p == 0.10


def test_slack_intents_offline() -> None:
    from surfaces.slack_bot import handle_request, parse_intent_fallback

    assert parse_intent_fallback("conquer NovaPay").company == "novapay.io"
    assert parse_intent_fallback("mark intro failed Elsa Jansen").kind == "mark_failed"
    text, blocks = asyncio.run(handle_request("conquer NovaPay"))
    assert "novapay" in text.lower() and blocks
    text, _ = asyncio.run(handle_request("mark intro failed Elsa Jansen"))
    assert "Rerouted" in text
