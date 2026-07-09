"""Content-analysis engine (Part A).

Reads the actual TEXT of interactions (Slack bodies, email bodies, Notion
notes, call transcripts) and extracts structured relationship substance:
sentiment, topics, commitments, risk flags, champion signals. Every row is
keyed on its source interaction id, so nothing is a naked claim.

Live path: claude-haiku-4-5 with a forced structured tool (cheap, high volume,
matches ACR_PRD section 8.1 model routing). Mock path: deterministic keyword
rules over the same text, so the whole thing runs on fixtures with no key.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fabric.store import (
    InteractionContextRow,
    InteractionRow,
    TranscriptRow,
    get_engine,
)

CONTENT_MODEL = "claude-haiku-4-5"
Sentiment = Literal["positive", "neutral", "negative", "tense"]

# Kinds whose `summary` carries real prose worth analyzing.
TEXT_KINDS = ("email", "slack", "note")


class ContentAnalysis(BaseModel):
    sentiment: Sentiment = "neutral"
    topics: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    champion_signals: list[str] = Field(default_factory=list)


# ---- deterministic mock rules -------------------------------------------------
_NEG = ("frustrat", "escalat", "outage", "at risk", "churn", "alternativ",
        "competitor", "cooled", "gone quiet", "not renew", "budget freeze",
        "slow response", "slipped", "hard to justify", "mistake")
_TENSE = ("escalat", "outage", "root cause", "no root cause")
_POS = ("thrilled", "excited", "impressed", "smooth", "best vendor", "love",
        "happy", "appreciate", "thank", "loved", "vouched", "great")
_CHAMP = ("champion", "vouch", "went to bat", "pushing the renewal", "pushes",
          "keeps pushing", "best vendor", "shared our case", "publicly vouched")
_RISK = ("competitor", "churn", "alternativ", "evaluate alternativ", "at risk",
         "escalat", "not renew", "outage", "budget freeze")
_TOPICS = {
    "pricing": ("pricing", "price", "cost", "budget", "invoice", "po number"),
    "renewal": ("renewal", "renew", "contract"),
    "support": ("support", "ticket", "response", "outage", "escalat"),
    "competitor": ("competitor", "alternativ", "switching"),
    "expansion": ("expand", "two more teams", "seat", "upsell"),
    "champion": ("champion", "vouch", "cfo", "cro", "leadership"),
    "product": ("dashboard", "product", "feature", "integration"),
}


def _hits(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def analyze_text_mock(text: str) -> ContentAnalysis:
    low = text.lower()
    if _hits(low, _TENSE):
        sentiment: Sentiment = "tense"
    elif _hits(low, _NEG):
        sentiment = "negative"
    elif _hits(low, _POS):
        sentiment = "positive"
    else:
        sentiment = "neutral"
    topics = [name for name, kws in _TOPICS.items() if _hits(low, kws)]
    commitments = []
    for cue in ("we said we", "we'll", "we will", "follow up by", "will send",
                "schedule", "confirm the po"):
        if cue in low:
            commitments.append(text.strip()[:140])
            break
    risk_flags = [text.strip()[:140]] if _hits(low, _RISK) else []
    champion_signals = [text.strip()[:140]] if _hits(low, _CHAMP) else []
    return ContentAnalysis(
        sentiment=sentiment,
        topics=topics,
        commitments=commitments,
        risk_flags=risk_flags,
        champion_signals=champion_signals,
    )


def llm_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


async def analyze_text(text: str) -> ContentAnalysis:
    if not llm_available():
        return analyze_text_mock(text)
    from agents.client import extract  # lazy; reuse the single Haiku wrapper

    prompt = (
        "Analyze this sales-relationship message. Extract sentiment "
        "(positive/neutral/negative/tense), topics mentioned, commitments made by "
        "either side, risk flags (churn/competitor/escalation language), and "
        "champion signals (someone vouching for us, or a champion going quiet). "
        f"Message:\n{text}"
    )
    result = await extract(prompt, ContentAnalysis, model=CONTENT_MODEL)
    return result  # type: ignore[return-value]


# ---- persistence + aggregation -----------------------------------------------
def _texts_for(session: Session, domain: str) -> list[tuple[str, str, str | None, datetime, str]]:
    """(interaction_id, text, person_id, ts, company_id) for analyzable rows."""
    cid = f"company:{domain.lower()}"
    out: list[tuple[str, str, str | None, datetime, str]] = []
    for r in (
        session.query(InteractionRow)
        .filter(InteractionRow.company_id == cid, InteractionRow.kind.in_(TEXT_KINDS))
        .all()
    ):
        if r.summary and len(r.summary) > 12:
            out.append((r.id, r.summary, r.person_id, r.ts, cid))
    for t in session.query(TranscriptRow).filter(TranscriptRow.company_id == cid).all():
        out.append((f"transcript:{t.id}", t.text, None, t.call_ts, cid))
    return out


async def analyze_account(session: Session, domain: str, limit: int | None = None) -> int:
    """Analyze (and persist) content for one account. Returns rows written."""
    rows = _texts_for(session, domain)
    rows.sort(key=lambda r: r[3], reverse=True)
    if limit:
        rows = rows[:limit]
    now = datetime.now()
    written = 0
    for interaction_id, text, person_id, ts, cid in rows:
        analysis = await analyze_text(text)
        session.merge(
            InteractionContextRow(
                interaction_id=interaction_id,
                company_id=cid,
                person_id=person_id,
                ts=ts,
                sentiment=analysis.sentiment,
                topics_json=json.dumps(analysis.topics),
                commitments_json=json.dumps(analysis.commitments),
                risk_flags_json=json.dumps(analysis.risk_flags),
                champion_signals_json=json.dumps(analysis.champion_signals),
                analyzed_at=now,
            )
        )
        written += 1
    session.commit()
    return written


_SENTIMENT_SCORE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0, "tense": -0.7}


def account_content_summary(session: Session, domain: str, recent: int = 8) -> dict[str, Any]:
    """Aggregate persisted content into a citable relationship signal for one
    account: mean sentiment, recent trend, champion signals, risk flags."""
    cid = f"company:{domain.lower()}"
    ctx = (
        session.query(InteractionContextRow)
        .filter(InteractionContextRow.company_id == cid)
        .order_by(InteractionContextRow.ts.desc())
        .all()
    )
    if not ctx:
        return {
            "analyzed": 0, "mean_sentiment": 0.0, "recent_sentiment": 0.0,
            "sentiment_trend": 0.0, "champion_signals": [], "risk_flags": [], "topics": [],
        }
    scores = [_SENTIMENT_SCORE[c.sentiment] for c in ctx]
    recent_scores = scores[:recent]
    older_scores = scores[recent:] or scores
    champs = [
        {"text": s, "interaction_id": c.interaction_id, "ts": c.ts.isoformat(timespec="seconds")}
        for c in ctx for s in json.loads(c.champion_signals_json)
    ]
    risks = [
        {"text": s, "interaction_id": c.interaction_id, "ts": c.ts.isoformat(timespec="seconds")}
        for c in ctx for s in json.loads(c.risk_flags_json)
    ]
    topics: dict[str, int] = {}
    for c in ctx:
        for t in json.loads(c.topics_json):
            topics[t] = topics.get(t, 0) + 1
    return {
        "analyzed": len(ctx),
        "mean_sentiment": round(sum(scores) / len(scores), 3),
        "recent_sentiment": round(sum(recent_scores) / len(recent_scores), 3),
        "sentiment_trend": round(
            sum(recent_scores) / len(recent_scores)
            - sum(older_scores) / len(older_scores), 3
        ),
        "champion_signals": champs[:5],
        "risk_flags": risks[:5],
        "topics": sorted(topics, key=topics.get, reverse=True)[:6],
    }


def analyze_all_accounts(domains: list[str] | None = None, limit: int | None = 12) -> int:
    """Batch pass over accounts (used by ingest/demo). Returns total rows."""
    import asyncio

    from fabric.store import CompanyRow

    async def run() -> int:
        total = 0
        with Session(get_engine()) as session:
            if domains is None:
                targets = [c.domain for c in session.query(CompanyRow).all()]
            else:
                targets = domains
            for dom in targets:
                total += await analyze_account(session, dom, limit=limit)
        return total

    return asyncio.run(run())
