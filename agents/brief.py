"""MeetingBrief assembler (Part B).

Composes the pre-call brief the Orbit frontend renders, from REAL backend data:
warmth (engines.warmth), interaction content analysis (engines.content, Part A),
the allocator's recommended action (engines.allocator), Sillage signals (live or
cached via fabric.sillage_provider), and Notion references. Maps to the Network
Agent MeetingBrief shape in ACR_PRD 8.2: context, references, upsells,
social_proof, evidence.

Mock-first: works on fixtures with zero credentials.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from engines import allocator as allocator_engine
from engines import content as content_engine
from engines import warmth as warmth_engine
from fabric import sillage_provider
from fabric.store import CompanyRow, ReferenceRow, SignalRow, get_engine


def _account_row(session: Session, domain: str) -> CompanyRow | None:
    return session.query(CompanyRow).filter(CompanyRow.domain == domain.lower()).first()


def _health_label(warmth: float, recent_sentiment: float, has_risk: bool) -> str:
    if has_risk or recent_sentiment <= -0.2:
        return "At risk"
    if warmth >= 0.6 and recent_sentiment >= 0.2:
        return "Healthy"
    return "Active"


def _recommended_action(domain: str) -> dict[str, Any] | None:
    """This account's best action from the allocator (unconstrained single-pick)."""
    with Session(get_engine()) as session:
        candidates = allocator_engine.build_candidates(session)
    mine = [c for c in candidates if c.domain == domain.lower() and c.u_eur > 0]
    if not mine:
        return None
    best = max(mine, key=lambda c: c.u_eur)
    return {"action": best.action, "u_eur": round(best.u_eur, 2), "components": best.components()}


def build_brief(domain: str) -> dict[str, Any]:
    """Assemble the MeetingBrief for one account. Returns a JSON-able dict."""
    domain = domain.lower()
    with Session(get_engine()) as session:
        company = _account_row(session, domain)
        is_insurer = sillage_provider.is_insurer(domain)
        meta = sillage_provider.account_meta(domain) or {}
        name = (company.name if company else meta.get("name")) or domain
        industry = (company.industry if company else meta.get("industry")) or ""
        arr = float(company.arr) if company and company.arr else 0.0

        # --- relationship health: warmth + content (Part A), evidence-backed ---
        heatmap = warmth_engine.company_heatmap(session, domain)  # analyzes + scores
        content = content_engine.account_content_summary(session, domain)
        if content["analyzed"] == 0:
            import asyncio

            asyncio.run(content_engine.analyze_account(session, domain, limit=12))
            content = content_engine.account_content_summary(session, domain)

        top_warmth = heatmap[0]["warmth"] if heatmap else 0.0
        has_risk = bool(content["risk_flags"])
        health = _health_label(top_warmth, content["recent_sentiment"], has_risk)

        champions = [
            {"text": c["text"], "evidence": c["interaction_id"]}
            for c in content["champion_signals"]
        ]
        risks = [
            {"text": c["text"], "evidence": c["interaction_id"]}
            for c in content["risk_flags"]
        ]
        sentiment_line = _sentiment_line(content)

        # --- signals: Sillage live/cached for insurers, DB signals otherwise ---
        if is_insurer:
            sig = sillage_provider.signals_for(domain)
            signal_source = sig["source"]
            signals = [
                {
                    "title": s["note"],
                    "kind": s["kind"],
                    "days": f"{s.get('days_ago', '?')}d",
                    "strength": s.get("strength"),
                    "talk": _signal_talk(s["kind"], s["note"]),
                    "id": s.get("id", ""),
                }
                for s in sig["signals"]
            ]
        else:
            signal_source = "store"
            rows = (
                session.query(SignalRow)
                .filter(
                    SignalRow.company_id == f"company:{domain}",
                    SignalRow.kind != "org_structure",  # org data, not a GTM signal
                )
                .order_by(SignalRow.ts.desc())
                .all()
            )
            import json as _json

            signals = [
                {
                    "title": _json.loads(r.payload_json).get("note", r.kind),
                    "kind": r.kind,
                    "days": f"{(datetime.now() - r.ts).days}d",
                    "strength": r.strength,
                    "talk": _signal_talk(r.kind, _json.loads(r.payload_json).get("note", "")),
                    "id": r.id,
                }
                for r in rows
            ]

        # --- upsell / recommended plays: warm contacts + allocator action ------
        action = _recommended_action(domain)
        upsells = []
        for row in heatmap[:3]:
            upsells.append(
                {
                    "name": row["person"],
                    "title": row["title"],
                    "warmth": row["warmth"],
                    # honest 'detect': how we know them, from real warmth components
                    "detect": _detect_line(row),
                    "in_crm": True,
                    "action": action["action"] if action else None,
                    "u_eur": action["u_eur"] if action else None,
                    "evidence": _warmth_evidence(row),
                }
            )

        # --- social proof: Notion references matching the account industry -----
        refs = (
            session.query(ReferenceRow)
            .filter(ReferenceRow.industry == industry)
            .all()
            if industry
            else []
        )
        references = [
            {"outcome": r.outcome, "quote": r.quote, "metric": r.metric,
             "product": r.product, "evidence": r.id}
            for r in refs
        ]

        # --- talking points ("say this on the call") ---------------------------
        talking_points = _talking_points(name, content, signals, action, champions)

        primary = heatmap[0] if heatmap else None
        return {
            "account": {
                "name": name,
                "domain": domain,
                "industry": industry,
                "arr_eur": arr,
                "health": health,
                "primary_contact": (
                    {"name": primary["person"], "title": primary["title"],
                     "warmth": primary["warmth"]}
                    if primary else None
                ),
                "signal_source": signal_source,
            },
            "context": _context_line(name, industry, arr, health, content),
            "relationship_health": {
                "warmth": round(top_warmth, 3),
                "recent_sentiment": content["recent_sentiment"],
                "sentiment_trend": content["sentiment_trend"],
                "sentiment_line": sentiment_line,
                "champion_signals": champions[:3],
                "risk_flags": risks[:3],
                "analyzed": content["analyzed"],
            },
            "upsells": upsells,
            "signals": signals,
            "talking_points": talking_points,
            "social_proof": references,
            # THE FINAL CASTLE: intentionally-empty slot. See web.py / Orbit.
            "fortress_slot": {
                "label": "Conquest map renders here",
                "data_contract": "engines.fortress.solve(domain, target) -> "
                "{target, v_deal, paths:[{steps:[{from,to,p,p_components}], R, effort, EV}]}",
                "populated": False,
            },
        }


# ---- small helpers ------------------------------------------------------------
def _sentiment_line(content: dict[str, Any]) -> str:
    if content["analyzed"] == 0:
        return "No interaction content analyzed yet."
    r = content["recent_sentiment"]
    if r <= -0.2:
        return f"Sentiment has cooled (recent {r:+.2f}) across {content['analyzed']} messages."
    if r >= 0.3:
        return f"Sentiment is warm (recent {r:+.2f}) across {content['analyzed']} messages."
    return f"Sentiment is steady ({r:+.2f})."


def _detect_line(row: dict[str, Any]) -> str:
    comp = row.get("components", {})
    freq = comp.get("freq_90d", 0)
    return f"{int(freq)} interactions in the last 90 days, warmth {row['warmth']:.2f}"


def _warmth_evidence(row: dict[str, Any]) -> str:
    comp = row.get("components", {})
    return (
        f"content_sentiment={comp.get('content_sentiment', 0):+.2f}, "
        f"reciprocity={comp.get('reciprocity', 0):.2f}"
    )


def _signal_talk(kind: str, note: str) -> str:
    templates = {
        "buying_intent": "They are actively researching - lead with the specific outcome.",
        "hiring_spike": "They are scaling the team - tie seat expansion to the new hires.",
        "champion_move": "Fresh leadership means fresh budget - anchor to their mandate.",
        "competitor_engagement": "A competitor is circling - preempt with your integration depth.",
        "job_change": "New decision-maker - reset the relationship early.",
        "champion_mention": "Your champion is active internally - equip them for the next meeting.",
    }
    return templates.get(kind, note or kind.replace("_", " "))


def _context_line(name: str, industry: str, arr: float, health: str, content: dict) -> str:
    bits = [f"{name}"]
    if industry:
        bits.append(f"({industry})")
    bits.append(f"- {health}.")
    if arr:
        bits.append(f"EUR {arr:,.0f} ARR.")
    bits.append(_sentiment_line(content))
    return " ".join(bits)


def _talking_points(
    name: str, content: dict, signals: list, action: dict | None, champions: list
) -> list[str]:
    points: list[str] = []
    if signals:
        points.append(signals[0]["talk"] + f"  ({signals[0]['kind']})")
    if champions:
        points.append(f"Reinforce your champion: {champions[0]['text'][:110]} "
                      f"[{champions[0]['evidence']}]")
    if content["recent_sentiment"] <= -0.2 and content["risk_flags"]:
        rf = content["risk_flags"][0]
        points.append(f"Address the cooling directly: {rf['text'][:110]} "
                      f"[{rf['interaction_id']}]")
    if action:
        points.append(f"Recommended next play: {action['action']} "
                      f"(worth EUR {action['u_eur']:,.0f} in expected uplift).")
    if not points:
        points.append(f"Open warm - {name} relationship is healthy; explore expansion.")
    return points
