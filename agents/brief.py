"""MeetingBrief assembler (Part B).

Composes the pre-call brief the Net-Work frontend renders, from REAL backend data:
warmth (engines.warmth), interaction content analysis (engines.content, Part A),
the allocator's recommended action (engines.allocator), Sillage signals (live or
cached via fabric.sillage_provider), and Notion references. Maps to the Network
Agent MeetingBrief shape in ACR_PRD 8.2: context, references, upsells,
social_proof, evidence.

Mock-first: works on fixtures with zero credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from engines import allocator as allocator_engine
from engines import content as content_engine
from engines import warmth as warmth_engine
from fabric import sillage_provider
from fabric.store import CompanyRow, ReferenceRow, SignalRow, get_engine


def _account_row(session: Session, domain: str) -> CompanyRow | None:
    return session.query(CompanyRow).filter(CompanyRow.domain == domain.lower()).first()


# ---- calendar of upcoming call slots -----------------------------------------
def _person_by_email(session: Session, email: str):
    from fabric.store import PersonRow

    return session.query(PersonRow).filter(PersonRow.email == email.lower()).first()


def _day_label(ts: datetime, now: datetime) -> str:
    delta = (ts.date() - now.date()).days
    return {0: "Today", 1: "Tomorrow"}.get(delta, ts.strftime("%A %d %b"))


def calendar(days: int = 7) -> list[dict[str, Any]]:
    """Upcoming call slots for the schedule view: one entry per scheduled call,
    resolved to the person you're meeting. Includes all of today's agenda."""
    from fabric import registry

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = now + timedelta(days=days)
    gcal = registry.get("gcal")
    slots = []
    with Session(get_engine()) as session:
        for ev in gcal.pull(since=None):
            p = ev.payload
            if not p.get("is_call_slot"):
                continue
            ts = datetime.fromisoformat(p["ts"])
            if not (today <= ts <= horizon):
                continue
            email = p.get("person_email", "")
            person = _person_by_email(session, email)
            company = _account_row(session, p["company_domain"])
            warmth = warmth_engine.get(session, f"person:{email.lower()}")
            slots.append(
                {
                    "event_id": p["id"],
                    "when": {
                        "iso": ts.isoformat(timespec="minutes"),
                        "day": _day_label(ts, now),
                        "time": ts.strftime("%H:%M"),
                        "sort": ts.isoformat(),
                    },
                    "purpose": p.get("purpose", p.get("title", "")),
                    "person": {
                        "email": email,
                        "name": person.full_name if person else email.split("@")[0].title(),
                        "title": person.title if person else "",
                    },
                    "company": {
                        "domain": p["company_domain"],
                        "name": company.name if company else p["company_domain"],
                    },
                    "warmth": round(warmth["score"], 2) if warmth else None,
                }
            )
    slots.sort(key=lambda s: s["when"]["sort"])
    return slots


def _health_label(warmth: float, recent_sentiment: float, has_risk: bool) -> str:
    if has_risk or recent_sentiment <= -0.2:
        return "At risk"
    if warmth >= 0.6 and recent_sentiment >= 0.2:
        return "Healthy"
    return "Active"


_ACTION_LABELS = {
    "qbr_review": "Run a QBR",
    "renewal_call": "Book the renewal call",
    "case_study_share": "Share a case study",
    "personalized_demo": "Run a personalized demo",
    "upsell_pitch": "Pitch the upsell",
    "exec_dinner": "Host an exec dinner",
    "onsite_workshop": "Run an onsite workshop",
    "champion_intro_ask": "Ask the champion for an intro",
    "swag_and_note": "Send swag + a personal note",
}


def _action_catalog() -> dict[str, Any]:
    import yaml

    from fabric.protocol import REPO_ROOT

    return yaml.safe_load(
        (REPO_ROOT / "config" / "actions.yaml").read_text(encoding="utf-8")
    )["actions"]


def _recommended_action(domain: str) -> dict[str, Any] | None:
    """This account's best action from the allocator (unconstrained single-pick)."""
    with Session(get_engine()) as session:
        candidates = allocator_engine.build_candidates(session)
    mine = [c for c in candidates if c.domain == domain.lower() and c.u_eur > 0]
    if not mine:
        return None
    best = max(mine, key=lambda c: c.u_eur)
    cost = _action_catalog().get(best.action, {})
    return {
        "action": best.action,
        "label": _ACTION_LABELS.get(best.action, best.action.replace("_", " ").title()),
        "u_eur": round(best.u_eur, 2),
        "hours": cost.get("hours", 0),
        "eur_cost": cost.get("eur", 0),
        "flavor": cost.get("flavor", ""),
        "components": best.components(),
    }


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
            # THE FINAL CASTLE: intentionally-empty slot. See web.py / the Net-Work frontend.
            "fortress_slot": {
                "label": "Conquest map renders here",
                "data_contract": "engines.fortress.solve(domain, target) -> "
                "{target, v_deal, paths:[{steps:[{from,to,p,p_components}], R, effort, EV}]}",
                "populated": False,
            },
        }


def book_of_business() -> list[dict[str, Any]]:
    """Portfolio view: every customer account with ARR, renewal, cadence, and
    the Part A content health (sentiment + risk), ranked at-risk first."""
    from agents.tools import portfolio_summary

    accounts = portfolio_summary()
    rows = []
    with Session(get_engine()) as session:
        for a in accounts:
            content = content_engine.account_content_summary(session, a["domain"])
            if content["analyzed"] == 0:
                import asyncio

                asyncio.run(content_engine.analyze_account(session, a["domain"], limit=8))
                content = content_engine.account_content_summary(session, a["domain"])
            sent = content["recent_sentiment"]
            # anchor to sentiment: a lone risk keyword in an otherwise-positive
            # account is not "at risk". Genuine cooling (or risk flags while
            # sentiment is not clearly positive) is.
            at_risk = sent <= -0.1 or (content["risk_flags"] and sent <= 0.1)
            health = (
                "At risk" if at_risk
                else "Healthy" if sent >= 0.35 and not content["risk_flags"]
                else "Active"
            )
            why = content["risk_flags"][0]["text"] if content["risk_flags"] else (
                f"{a['days_silent']}d since last touch" if a["days_silent"] > 45 else
                "sentiment " + f"{content['recent_sentiment']:+.2f}"
            )
            rows.append(
                {
                    "account": a["account"],
                    "domain": a["domain"],
                    "arr_eur": a["arr_eur"],
                    "renewal_date": a["renewal_date"],
                    "days_silent": a["days_silent"],
                    "interactions_90d": a["interactions_90d"],
                    "recent_sentiment": content["recent_sentiment"],
                    "health": health,
                    "why": why,
                }
            )
    rank = {"At risk": 0, "Active": 1, "Healthy": 2}
    rows.sort(key=lambda r: (rank[r["health"]], -r["arr_eur"]))
    return rows


_SENIORITY_RANK = {"IC": 0, "MGR": 1, "DIR": 2, "VP": 3, "C": 4}


def _onward_intros(session: Session, person_id: str, domain: str) -> list[dict[str, Any]]:
    """Who this person can introduce you to: their org-graph neighbours, ranked
    by the value of the target (seniority) times how reachable the intro is."""
    from engines import fortress
    from fabric.store import OrgEdgeRow, PersonRow

    # ensure org edges are materialized for this company (idempotent)
    if (
        session.query(OrgEdgeRow)
        .join(PersonRow, PersonRow.id == OrgEdgeRow.src_person)
        .filter(PersonRow.company_id == f"company:{domain.lower()}")
        .count()
        == 0
    ):
        fortress.build_org_edges(session, domain)

    import json as _json

    out = []
    for edge in session.query(OrgEdgeRow).filter(OrgEdgeRow.src_person == person_id).all():
        dst = session.get(PersonRow, edge.dst_person)
        if not dst:
            continue
        rank = _SENIORITY_RANK.get(dst.seniority_level, 0)
        score = rank * edge.p_uv
        out.append(
            {
                "name": dst.full_name,
                "title": dst.title,
                "seniority": dst.seniority_level,
                "rel_type": edge.rel_type,
                "reachability": round(edge.p_uv, 3),
                "reason": _intro_reason(edge.rel_type, dst),
                "source": _intro_source(edge.rel_type),
                "incentive": _intro_incentive(score),
                "score": round(score, 3),
                "p_components": _json.loads(edge.p_components_json),
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    # prefer higher-value targets (VP/C), drop peers/ICs unless nothing else
    strong = [o for o in out if o["seniority"] in ("DIR", "VP", "C")]
    return (strong or out)[:4]


def _intro_reason(rel_type: str, dst) -> str:
    who = f"{dst.full_name} ({dst.title})"
    return {
        "manages": f"Their manager {who} - the fastest line to a decision.",
        "skip": f"{who} sits two levels up - a warm skip-level intro.",
        "peer": f"{who} is a peer they trust - lateral expansion.",
        "cross_dept": f"{who} leads another function - widen the footprint.",
        "external_mutual": f"{who} - a mutual connection.",
    }.get(rel_type, who)


# where the recommendation itself came from, so a rep can judge how solid it is
_INTRO_SOURCES = {
    "manages": {"kind": "enr", "mark": "F", "label": "FullEnrich org chart"},
    "skip": {"kind": "enr", "mark": "F", "label": "FullEnrich org chart"},
    "peer": {"kind": "enr", "mark": "F", "label": "FullEnrich org chart"},
    "cross_dept": {"kind": "enr", "mark": "F", "label": "FullEnrich org chart"},
    "external_mutual": {"kind": "li", "mark": "in", "label": "LinkedIn comment"},
}


def _intro_source(rel_type: str) -> dict[str, str]:
    return _INTRO_SOURCES.get(
        rel_type, {"kind": "enr", "mark": "F", "label": "FullEnrich org chart"}
    )


# suggested thank-you incentive for the introducer, scaled to the actual
# value of the ask (seniority reached x how reachable the intro is) — not
# just the target's title. A C-level intro nobody can actually reach is
# worth a gift box, not a weekend away; a highly-reachable exec intro is.
def _intro_incentive(score: float) -> dict[str, str]:
    if score >= 2.5:
        return {"icon": "🏝️", "label": "Weekend getaway"}
    if score >= 1.0:
        return {"icon": "🍽️", "label": "Dinner"}
    return {"icon": "🎁", "label": "Gift box"}


def build_person_brief(email: str) -> dict[str, Any]:
    """One-pager for a specific person you're about to call: who they are, our
    relationship with them, and who to ask them to introduce you to."""
    email = email.lower()
    with Session(get_engine()) as session:
        person = _person_by_email(session, email)
        if person is None:
            return {"error": f"no person {email}"}
        domain = (person.company_id or "company:").split(":", 1)[-1]
        company = _account_row(session, domain)
        warmth = warmth_engine.get(session, person.id)

        # relationship substance (Part A), account-level, cited
        content = content_engine.account_content_summary(session, domain)
        if content["analyzed"] == 0:
            import asyncio

            asyncio.run(content_engine.analyze_account(session, domain, limit=12))
            content = content_engine.account_content_summary(session, domain)

        # this person's own thread sentiment, if we have analyzed content for them
        from fabric.store import InteractionContextRow

        pctx = (
            session.query(InteractionContextRow)
            .filter(InteractionContextRow.person_id == person.id)
            .all()
        )
        smap = {"positive": 1.0, "neutral": 0.0, "negative": -1.0, "tense": -0.7}
        person_sentiment = (
            round(sum(smap[c.sentiment] for c in pctx) / len(pctx), 2) if pctx else None
        )

        # the scheduled purpose for this person, if a call slot exists
        purpose = ""
        for slot in calendar(days=14):
            if slot["person"]["email"] == email:
                purpose = slot["purpose"]
                break

        onward = _onward_intros(session, person.id, domain)

        champions = [
            {"text": c["text"], "evidence": c["interaction_id"]}
            for c in content["champion_signals"]
        ]
        risks = [
            {"text": c["text"], "evidence": c["interaction_id"]}
            for c in content["risk_flags"]
        ]
        health = _health_label(
            warmth["score"] if warmth else 0.0, content["recent_sentiment"], bool(risks)
        )
        return {
            "person": {
                "name": person.full_name,
                "title": person.title,
                "dept": person.dept,
                "seniority": person.seniority_level,
                "email": person.email,
                "phone": person.phone or "",
                "company": company.name if company else domain,
                "domain": domain,
            },
            "purpose": purpose,
            "health": health,
            "relationship": {
                "warmth": round(warmth["score"], 3) if warmth else 0.0,
                "warmth_components": warmth["components"] if warmth else {},
                "person_sentiment": person_sentiment,
                "account_recent_sentiment": content["recent_sentiment"],
                "sentiment_line": _sentiment_line(content),
                "champion_signals": champions[:3],
                "risk_flags": risks[:3],
            },
            # THE ASK: who to have this person introduce you to
            "onward_intros": onward,
            # THE NEXT BASE ACTION: allocator's top pick for this account
            "next_action": _recommended_action(domain),
            "context": (
                f"{person.full_name} - {person.title} at "
                f"{company.name if company else domain}. "
                + (f"Purpose: {purpose}. " if purpose else "")
                + _sentiment_line(content)
            ),
            "fortress_slot": {
                "label": "Conquest map renders here",
                "data_contract": "engines.fortress.solve(domain, target) -> "
                "{target, v_deal, paths:[{steps:[{from,to,p,p_components}], R, effort, EV}]}",
                "populated": False,
            },
        }


def _script_fallback(pb: dict[str, Any]) -> str:
    """Deterministic calling script when no ANTHROPIC_API_KEY is set: same
    structure the live model produces, built straight off the brief."""
    p, rel = pb["person"], pb["relationship"]
    lines = [
        f"Call script — {p['name']} ({p['title']}, {p['company']})",
        "",
        "OPEN",
        f"\"Hi {p['name'].split()[0]}, thanks for making time"
        + (
            f" — I wanted to talk through {pb['purpose'].lower()}.\""
            if pb.get("purpose")
            else '."'
        ),
        "",
        "RELATIONSHIP CHECK-IN",
        f"\"{rel['sentiment_line']}\"",
    ]
    for c in rel.get("champion_signals", [])[:1]:
        lines.append(f"  - Reinforce: {c['text']} [{c['evidence']}]")
    for r in rel.get("risk_flags", [])[:1]:
        lines.append(f"  - Address directly: {r['text']} [{r['evidence']}]")
    lines += ["", "AGENDA", f"\"{pb.get('purpose') or 'Catch up on where things stand.'}\""]
    onward = pb.get("onward_intros") or []
    if onward:
        top = onward[0]
        lines += [
            "",
            "THE ASK — request an introduction",
            f"\"One more thing — would you be open to introducing me to {top['name']}"
            f" ({top['title']})? {top['reason']}\"",
            f"  - Source: {top['source']['label']}",
            f"  - Suggested thank-you: {top['incentive']['icon']} {top['incentive']['label']}"
            f" once the intro lands.",
        ]
        for o in onward[1:3]:
            lines.append(f"  - Fallback ask: {o['name']} ({o['title']}) — {o['reason']}")
    lines += ["", "CLOSE", "\"Appreciate the time — I'll follow up with next steps by email.\""]
    return "\n".join(lines)


async def _script_live(pb: dict[str, Any]) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic()
    onward = pb.get("onward_intros") or []
    prompt = (
        "Write a short, natural sales call script (not a transcript, a rep's talk track "
        "with section headers) for the call below. Keep it under 200 words. "
        "It MUST include an explicit, specific ask for an introduction to the top "
        "recommended contact, referencing why (their reason) and where that "
        "recommendation came from (their source), and suggest the thank-you incentive "
        "listed for them.\n\n"
        f"Person: {pb['person']['name']}, {pb['person']['title']} at {pb['person']['company']}\n"
        f"Purpose: {pb.get('purpose', 'general check-in')}\n"
        f"Relationship: {pb['relationship']['sentiment_line']}\n"
        f"Champion signals: {[c['text'] for c in pb['relationship'].get('champion_signals', [])]}\n"
        f"Risk flags: {[r['text'] for r in pb['relationship'].get('risk_flags', [])]}\n"
        f"Top intro to ask for: {onward[0] if onward else 'none available'}\n"
    )
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def build_call_script(email: str) -> dict[str, Any]:
    """Talk-track for the upcoming call, ending with an explicit ask for an
    introduction to the best onward contact. Live model with ANTHROPIC_API_KEY,
    deterministic fallback otherwise."""
    import asyncio
    import os

    pb = build_person_brief(email)
    if "error" in pb:
        return pb
    if os.getenv("ANTHROPIC_API_KEY"):
        script = asyncio.run(_script_live(pb))
        source = "claude-haiku-4-5"
    else:
        script = _script_fallback(pb)
        source = "template"
    return {"person": pb["person"]["name"], "script": script, "source": source}


# ---- next base action: in-depth plan + email draft + meeting proposal --------
def _action_plan_fallback(pb: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Deterministic plan when no ANTHROPIC_API_KEY is set."""
    p, rel = pb["person"], pb["relationship"]
    first = p["name"].split()[0]
    steps = [
        f"Confirm the goal internally: {action['label']} to capture "
        f"€{action['u_eur']:,.0f} in expected uplift ({action['flavor']}).",
        f"Reference the relationship signal: {rel['sentiment_line']}",
    ]
    if rel.get("champion_signals"):
        steps.append(
            f"Loop in the champion: {rel['champion_signals'][0]['text'][:100]} "
            f"[{rel['champion_signals'][0]['evidence']}]"
        )
    if rel.get("risk_flags"):
        steps.append(f"Neutralize the risk first: {rel['risk_flags'][0]['text'][:100]}")
    steps.append("Send the outreach email and propose a slot within the next 5 business days.")
    steps.append("Log the outcome and update warmth after the touch.")

    subject = f"{action['label']} — {p['company']}"
    body = (
        f"Hi {first},\n\n"
        f"{rel['sentiment_line']} Given where things stand, I'd like to "
        f"{action['label'].lower()} together"
        + (f" — this ties directly to {pb['purpose'].lower()}." if pb.get("purpose") else ".")
        + f"\n\nDoes {_next_business_slot()} work for a {action['hours']:.0f}h session?"
        f"\n\nBest,\nYour rep"
    )
    return {
        "rationale": f"Top allocator pick for {p['company']}: {action['label']} "
        f"(€{action['u_eur']:,.0f} expected uplift, {action['flavor']}, "
        f"~{action['hours']:.0f}h / €{action['eur_cost']:.0f} cost).",
        "steps": steps,
        "email_draft": {"subject": subject, "body": body},
        "meeting_proposal": {
            "when": _next_business_slot(),
            "duration_mins": int(action["hours"] * 60) or 30,
            "agenda": f"{action['label']} — {pb.get('purpose') or p['company']}",
        },
        "source": "template",
    }


async def _action_plan_live(pb: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    import anthropic

    from agents.schemas import ActionPlan

    client = anthropic.AsyncAnthropic()
    p, rel = pb["person"], pb["relationship"]
    prompt = (
        "Build an in-depth, actionable next-step plan for a B2B sales rep. "
        f"Recommended action: {action['label']} (flavor {action['flavor']}, "
        f"expected uplift EUR {action['u_eur']:.0f}, cost {action['hours']}h / "
        f"EUR {action['eur_cost']}).\n"
        f"Contact: {p['name']}, {p['title']} at {p['company']}.\n"
        f"Relationship: {rel['sentiment_line']}\n"
        f"Champion signals: {[c['text'] for c in rel.get('champion_signals', [])]}\n"
        f"Risk flags: {[r['text'] for r in rel.get('risk_flags', [])]}\n"
        f"Purpose of next call: {pb.get('purpose', 'general check-in')}\n\n"
        "Return: a one-sentence rationale, 3-5 concrete numbered steps, a short "
        "email draft (subject + body, first-person from the rep) proposing this "
        "action, and a meeting proposal (a specific relative day/time like "
        "'Thursday 14:00', duration in minutes, one-line agenda)."
    )
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=900,
        tools=[
            {
                "name": "action_plan",
                "description": "Submit the structured action plan.",
                "input_schema": ActionPlan.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "action_plan"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    plan = ActionPlan.model_validate(block.input)
    return {
        "rationale": plan.rationale,
        "steps": plan.steps,
        "email_draft": {"subject": plan.email_subject, "body": plan.email_body},
        "meeting_proposal": {
            "when": plan.meeting_when,
            "duration_mins": plan.meeting_duration_mins,
            "agenda": plan.meeting_agenda,
        },
        "source": "claude-haiku-4-5",
    }


def _next_business_slot() -> str:
    from datetime import timedelta

    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%A %H:00").replace("%H:00", "14:00")


def build_action_plan(email: str) -> dict[str, Any]:
    """In-depth plan for the account's top allocator-recommended action:
    rationale, concrete steps, a ready-to-send email draft, and a meeting
    proposal. Live model with ANTHROPIC_API_KEY, deterministic fallback
    otherwise."""
    import asyncio
    import os

    pb = build_person_brief(email)
    if "error" in pb:
        return pb
    action = pb.get("next_action")
    if not action:
        return {"error": f"no recommended action for {pb['person']['company']}"}
    if os.getenv("ANTHROPIC_API_KEY"):
        plan = asyncio.run(_action_plan_live(pb, action))
    else:
        plan = _action_plan_fallback(pb, action)
    plan["action"] = action
    plan["person"] = pb["person"]["name"]
    return plan


def send_email(to_email: str, subject: str, body: str) -> dict[str, Any]:
    """Mock send: no live Gmail-send scope is wired (README: gmail.readonly
    only), so this simulates the send and returns a confirmation the UI can
    show. Swap for a real Gmail API call once send scope + credentials exist."""
    return {
        "status": "sent (mock)",
        "to": to_email,
        "subject": subject,
        "sent_at": datetime.now().isoformat(timespec="minutes"),
    }


def book_meeting(
    email: str, when: str, duration_mins: int = 30, agenda: str = ""
) -> dict[str, Any]:
    """Mock booking: no live GCal-write scope is wired, so this simulates the
    booking and returns a confirmation. Swap for a real GCal insert once
    write credentials exist."""
    return {
        "status": "booked (mock)",
        "person": email,
        "when": when,
        "duration_mins": duration_mins,
        "agenda": agenda,
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
