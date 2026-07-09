"""Warmth engine.

w(person) = sigmoid(a1*recency_decay + a2*ln(1+freq_90d) + a3*reciprocity
                    + a4*seniority_touch + a5*channel_diversity + bias)
Exponential recency decay with a 30-day half-life. Coefficients live in
config/warmth.yaml and every score stores its components_json sibling.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

import yaml
from sqlalchemy.orm import Session

from fabric.protocol import REPO_ROOT
from fabric.store import CompanyRow, InteractionRow, PersonRow, WarmthRow

CONFIG_PATH = REPO_ROOT / "config" / "warmth.yaml"


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def components_for(
    person: PersonRow,
    interactions: list[InteractionRow],
    now: datetime,
    cfg: dict[str, Any],
    content: dict[str, float] | None = None,
) -> dict[str, float]:
    half_life = float(cfg["half_life_days"])
    sw = cfg["seniority_weights"]
    if interactions:
        days_since = min((now - i.ts).total_seconds() / 86400 for i in interactions)
        recency = 2.0 ** (-days_since / half_life)
    else:
        recency = 0.0
    recent = [i for i in interactions if i.ts >= now - timedelta(days=90)]
    freq_90d = float(len(recent))
    inbound = sum(1 for i in interactions if i.direction == "inbound")
    outbound = sum(1 for i in interactions if i.direction == "outbound")
    total = inbound + outbound
    reciprocity = (2.0 * min(inbound, outbound) / total) if total else 0.0
    seniority_touch = float(sw.get(person.seniority_level, 0.2)) if interactions else 0.0
    channel_diversity = len({i.kind for i in interactions}) / 5.0
    content = content or {}
    return {
        "recency_decay": round(recency, 4),
        "freq_90d": freq_90d,
        "reciprocity": round(reciprocity, 4),
        "seniority_touch": seniority_touch,
        "channel_diversity": round(channel_diversity, 4),
        # Part A: substance of the interactions, not just their cadence.
        "content_sentiment": round(float(content.get("content_sentiment", 0.0)), 4),
        "champion": round(float(content.get("champion", 0.0)), 4),
    }


def score_person(
    person: PersonRow,
    interactions: list[InteractionRow],
    now: datetime | None = None,
    content: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    cfg = _config()
    now = now or datetime.now()
    comp = components_for(person, interactions, now, cfg, content)
    a = cfg["coefficients"]
    z = (
        a["a1_recency"] * comp["recency_decay"]
        + a["a2_frequency"] * math.log1p(comp["freq_90d"])
        + a["a3_reciprocity"] * comp["reciprocity"]
        + a["a4_seniority_touch"] * comp["seniority_touch"]
        + a["a5_channel_diversity"] * comp["channel_diversity"]
        + a.get("a6_content_sentiment", 0.0) * comp["content_sentiment"]
        + a.get("a7_champion", 0.0) * comp["champion"]
        + a["bias"]
    )
    return _sigmoid(z), comp


def _content_maps(
    session: Session, company_domain: str | None
) -> tuple[dict[str, float], dict[str, float]]:
    """Per-person mean content sentiment and per-account champion strength,
    derived from the interaction_context table. Empty if content not analyzed
    (so warmth gracefully falls back to metadata-only)."""
    from fabric.store import InteractionContextRow

    score_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0, "tense": -0.7}
    q = session.query(InteractionContextRow)
    if company_domain:
        q = q.filter(InteractionContextRow.company_id == f"company:{company_domain.lower()}")
    per_person: dict[str, list[float]] = {}
    champ_count: dict[str, int] = {}
    for c in q.all():
        if c.person_id:
            per_person.setdefault(c.person_id, []).append(score_map[c.sentiment])
        # Only a POSITIVE champion signal lifts warmth. A champion "going quiet"
        # is a risk (negative/tense sentiment) and must not count as a vouch.
        if (
            c.champion_signals_json and c.champion_signals_json != "[]"
            and c.sentiment in ("positive", "neutral")
        ):
            champ_count[c.company_id] = champ_count.get(c.company_id, 0) + 1
    person_sent = {pid: sum(v) / len(v) for pid, v in per_person.items()}
    champ = {cid: min(1.0, n / 2.0) for cid, n in champ_count.items()}
    return person_sent, champ


def compute_all(
    session: Session, company_domain: str | None = None, use_content: bool = True
) -> list[WarmthRow]:
    """Score every person (optionally one company) and persist to warmth.

    use_content=False computes the metadata-only score (the pre-Part-A baseline),
    used to prove content analysis changes the number, not just decorates it.
    """
    now = datetime.now()
    person_sent, champ = _content_maps(session, company_domain) if use_content else ({}, {})
    query = session.query(PersonRow)
    if company_domain:
        query = query.filter(PersonRow.company_id == f"company:{company_domain.lower()}")
    rows: list[WarmthRow] = []
    for person in query.all():
        interactions = (
            session.query(InteractionRow).filter(InteractionRow.person_id == person.id).all()
        )
        content = {
            "content_sentiment": person_sent.get(person.id, 0.0),
            "champion": champ.get(person.company_id, 0.0),
        }
        score, comp = score_person(person, interactions, now, content)
        row = WarmthRow(
            person_id=person.id,
            score=round(score, 4),
            components_json=json.dumps(comp, sort_keys=True),
            computed_at=now,
        )
        session.merge(row)
        rows.append(row)
    session.commit()
    return rows


def get(session: Session, person_id: str) -> dict[str, Any] | None:
    """MCP tool: warmth score + components for one person id."""
    row = session.get(WarmthRow, person_id)
    if row is None:
        return None
    return {
        "person_id": row.person_id,
        "score": row.score,
        "components": json.loads(row.components_json),
        "computed_at": row.computed_at.isoformat(timespec="seconds"),
    }


def company_heatmap(session: Session, company_domain: str) -> list[dict[str, Any]]:
    """Heatmap-ready rows for a company, warmest first."""
    compute_all(session, company_domain)
    cid = f"company:{company_domain.lower()}"
    out = []
    for person, warm in (
        session.query(PersonRow, WarmthRow)
        .join(WarmthRow, WarmthRow.person_id == PersonRow.id)
        .filter(PersonRow.company_id == cid)
        .order_by(WarmthRow.score.desc())
        .all()
    ):
        out.append(
            {
                "person": person.full_name,
                "title": person.title,
                "dept": person.dept,
                "seniority": person.seniority_level,
                "warmth": warm.score,
                "components": json.loads(warm.components_json),
            }
        )
    return out


def _company_domain_exists(session: Session, domain: str) -> bool:
    return session.query(CompanyRow).filter(CompanyRow.domain == domain.lower()).count() > 0
