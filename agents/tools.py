"""The MCP tool surface exposed to agents. Direct Python calls hit the same
connector and engine code the MCP servers wrap."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from engines import allocator, fortress
from engines import warmth as warmth_engine
from fabric import registry
from fabric.store import CompanyRow, InteractionRow, SignalRow, TranscriptRow, get_engine


def enrich_company(domain: str) -> dict[str, Any]:
    """Org structure, people, and warm nodes for a company domain."""
    return registry.get("fullenrich").enrich_company(domain)


def warmth_heatmap(domain: str) -> list[dict[str, Any]]:
    """Warmth-ranked people at a company with score components."""
    with Session(get_engine()) as session:
        return warmth_engine.company_heatmap(session, domain)


def signals_for(domain: str) -> list[dict[str, Any]]:
    """All stored signals for a company domain."""
    with Session(get_engine()) as session:
        rows = (
            session.query(SignalRow)
            .filter(SignalRow.company_id == f"company:{domain.lower()}")
            .all()
        )
        return [
            {
                "id": r.id,
                "source": r.source,
                "kind": r.kind,
                "strength": r.strength,
                "ts": r.ts.isoformat(timespec="seconds"),
                "payload": json.loads(r.payload_json),
            }
            for r in rows
        ]


def fortress_solve(domain: str, target: str, v_deal: float = 50_000.0) -> dict[str, Any]:
    """Top-3 most reliable intro paths to a target title."""
    return fortress.solve(domain, target, v_deal)


def fortress_fail_edge(
    domain: str, target: str, from_person: str, to_person: str, v_deal: float = 50_000.0
) -> dict[str, Any]:
    """Fail an intro edge and re-solve."""
    return fortress.fail_edge(domain, target, from_person, to_person, v_deal)


def allocator_solve(hours: float = 8.0, eur: float = 900.0) -> dict[str, Any]:
    """MCKP allocation plan under budgets."""
    return allocator.solve(hours, eur)


def transcripts_for(domain: str) -> list[dict[str, Any]]:
    """Raw call transcripts for a company."""
    with Session(get_engine()) as session:
        rows = (
            session.query(TranscriptRow)
            .filter(TranscriptRow.company_id == f"company:{domain.lower()}")
            .all()
        )
        return [
            {"id": r.id, "call_ts": r.call_ts.isoformat(timespec="seconds"), "text": r.text}
            for r in rows
        ]


def portfolio_summary() -> list[dict[str, Any]]:
    """Customer accounts with ARR, renewal, and recent interaction stats."""
    now = datetime.now()
    with Session(get_engine()) as session:
        out = []
        for company in (
            session.query(CompanyRow).filter(CompanyRow.is_customer.is_(True)).all()
        ):
            last = (
                session.query(InteractionRow)
                .filter(InteractionRow.company_id == company.id)
                .order_by(InteractionRow.ts.desc())
                .first()
            )
            days_silent = (now - last.ts).days if last else 999
            recent = (
                session.query(InteractionRow)
                .filter(
                    InteractionRow.company_id == company.id,
                    InteractionRow.ts >= now - timedelta(days=90),
                )
                .count()
            )
            out.append(
                {
                    "account": company.name,
                    "domain": company.domain,
                    "arr_eur": company.arr,
                    "renewal_date": company.renewal_date.isoformat(timespec="seconds")
                    if company.renewal_date
                    else None,
                    "days_silent": days_silent,
                    "interactions_90d": recent,
                }
            )
        out.sort(key=lambda a: a["arr_eur"], reverse=True)
        return out


def recent_context(domain: str, n: int = 5) -> dict[str, Any]:
    """Last n interactions plus signals for one account (allocator adjustment)."""
    with Session(get_engine()) as session:
        rows = (
            session.query(InteractionRow)
            .filter(InteractionRow.company_id == f"company:{domain.lower()}")
            .order_by(InteractionRow.ts.desc())
            .limit(n)
            .all()
        )
        return {
            "interactions": [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "ts": r.ts.isoformat(timespec="seconds"),
                    "direction": r.direction,
                    "sentiment": r.sentiment,
                    "summary": r.summary,
                }
                for r in rows
            ],
            "signals": signals_for(domain),
            "content_analysis": content_summary(domain),
        }


def content_summary(domain: str) -> dict[str, Any]:
    """Content-analysis of an account's interactions (Part A): mean/recent
    sentiment, cooling trend, champion signals and risk flags, each cited to a
    source interaction id. Analyzes on demand if not yet cached."""
    from engines import content as content_engine

    with Session(get_engine()) as session:
        summary = content_engine.account_content_summary(session, domain)
        if summary["analyzed"] == 0:
            import asyncio

            asyncio.run(content_engine.analyze_account(session, domain, limit=12))
            summary = content_engine.account_content_summary(session, domain)
        return summary


NETWORK_TOOLS = {
    "enrich_company": enrich_company,
    "warmth_heatmap": warmth_heatmap,
    "signals_for": signals_for,
    "content_summary": content_summary,
}
RELATIONSHIP_TOOLS = {
    "portfolio_summary": portfolio_summary,
    "signals_for": signals_for,
    "content_summary": content_summary,
}
CONQUEST_TOOLS = {
    "fortress_solve": fortress_solve,
    "fortress_fail_edge": fortress_fail_edge,
    "signals_for": signals_for,
    "transcripts_for": transcripts_for,
}
