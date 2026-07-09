"""Deterministic mock agents: same tool calls, same event choreography, and
schema-identical outputs, computed from fixtures instead of a model. Keeps the
full Phase 3/4 demo runnable with an empty .env."""

from __future__ import annotations

from agents import schemas as S
from agents import tools as T
from agents.bus import EventBus


def mock_network(target: str, bus: EventBus) -> S.NetworkReport:
    bus.moved_to("Network", "org-map")
    bus.asks("Network", f"enrich_company({target})")
    block = T.enrich_company(target)
    bus.receives("Network", f"{len(block['people'])} people, {len(block['warm_nodes'])} warm")
    bus.asks("Network", f"warmth_heatmap({target})")
    heat = T.warmth_heatmap(target)
    bus.receives("Network", f"heatmap of {len(heat)} people")
    bus.asks("Network", f"signals_for({target})")
    signals = T.signals_for(target)
    bus.receives("Network", f"{len(signals)} signals")
    by_email = {p["email"]: p for p in block["people"]}
    warm_nodes = [
        S.WarmNode(
            name=row["person"],
            title=row["title"],
            warmth=row["warmth"],
            why=f"freq_90d={row['components']['freq_90d']}, "
            f"reciprocity={row['components']['reciprocity']}",
        )
        for row in heat
        if row["warmth"] >= 0.35
    ][:6]
    power = [p["full_name"] for p in block["people"] if p["seniority_level"] in ("C", "VP")]
    champions = [
        f"{by_email.get(s.get('payload', {}).get('person_email', ''), {}).get('full_name', '')}"
        f"{s['payload'].get('note', '')} [{s['id']}]"
        for s in signals
        if s["kind"] == "champion_move"
    ]
    return S.NetworkReport(
        target=target,
        warm_nodes=warm_nodes,
        power_centers=power,
        champion_notes=champions,
        summary=f"{len(warm_nodes)} warm nodes into {target}; power center is the "
        f"C-suite ({len(power)} execs). Champion move detected: enter via Finance.",
    )


def mock_relationship(bus: EventBus) -> S.RelationshipReport:
    bus.moved_to("Relationship", "portfolio")
    bus.asks("Relationship", "portfolio_summary()")
    accounts = T.portfolio_summary()
    bus.receives("Relationship", f"{len(accounts)} accounts")
    risks = []
    for account in accounts:
        evidence = []
        if account["days_silent"] >= 60 and account["arr_eur"] >= 100_000:
            evidence.append(f"{account['days_silent']} days of email silence")
        signals = T.signals_for(account["domain"])
        comp = [s for s in signals if s["kind"] == "competitor_engagement"]
        if comp:
            evidence.append(f"competitor touch [{comp[0]['id']}]")
        if evidence:
            bus.asks("Relationship", f"signals_for({account['domain']})")
            bus.receives("Relationship", f"{len(signals)} signals")
            risks.append(
                S.RetentionRisk(
                    account=account["account"],
                    arr_eur=account["arr_eur"],
                    risk="; ".join(evidence),
                    evidence=evidence,
                )
            )
    risks.sort(key=lambda r: r.arr_eur, reverse=True)
    return S.RelationshipReport(
        risks=risks[:5],
        summary=f"{len(risks)} accounts at risk, EUR "
        f"{sum(r.arr_eur for r in risks):,.0f} ARR exposed.",
    )


def mock_conquest(target: str, objective: str, bus: EventBus) -> S.ConquestReport:
    bus.moved_to("Conquest", "fortress")
    bus.asks("Conquest", f"fortress_solve({target}, {objective})")
    solved = T.fortress_solve(target, objective, v_deal=100_000)
    bus.receives("Conquest", f"{len(solved['paths'])} paths, best R={solved['paths'][0]['R']}")
    bus.asks("Conquest", f"signals_for({target})")
    signals = T.signals_for(target)
    bus.receives("Conquest", f"{len(signals)} signals")
    bus.asks("Conquest", f"transcripts_for({target})")
    transcripts = T.transcripts_for(target)
    bus.receives("Conquest", f"{len(transcripts)} transcripts")

    def play(path: dict) -> S.ConquestPlay:
        timing = next((s for s in signals if s["kind"] in ("hiring_spike", "buying_intent")), None)
        return S.ConquestPlay(
            steps=[
                S.ConquestStep(
                    from_person=s["from"],
                    to_person=s["to"],
                    ask=f"warm intro toward {solved['target']['name']}",
                    p=s["p"],
                )
                for s in path["steps"]
            ],
            reliability=path["R"],
            ev_eur=path["EV"],
            timing_signal=f"{timing['payload']['note']} [{timing['id']}]" if timing else "",
        )

    objections = []
    for t in transcripts:
        for line in t["text"].split("\n"):
            low = line.lower()
            if line.startswith("Prospect:") and (
                "worries" in low or "concern" in low or "skeptical" in low
            ):
                objections.append(f"{line.split(':', 1)[1].strip()} [{t['id']}]")
    paths = solved["paths"]
    return S.ConquestReport(
        target=target,
        objective=objective,
        primary_play=play(paths[0]),
        fallback_play=play(paths[1]) if len(paths) > 1 else None,
        objections=objections,
        summary=f"Primary path R={paths[0]['R']} EV=EUR {paths[0]['EV']:,.0f}; "
        f"{len(objections)} objections to pre-empt from call history.",
    )
