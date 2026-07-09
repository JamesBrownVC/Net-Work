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
    person: PersonRow, interactions: list[InteractionRow], now: datetime, cfg: dict[str, Any]
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
    return {
        "recency_decay": round(recency, 4),
        "freq_90d": freq_90d,
        "reciprocity": round(reciprocity, 4),
        "seniority_touch": seniority_touch,
        "channel_diversity": round(channel_diversity, 4),
    }


def score_person(
    person: PersonRow, interactions: list[InteractionRow], now: datetime | None = None
) -> tuple[float, dict[str, float]]:
    cfg = _config()
    now = now or datetime.now()
    comp = components_for(person, interactions, now, cfg)
    a = cfg["coefficients"]
    z = (
        a["a1_recency"] * comp["recency_decay"]
        + a["a2_frequency"] * math.log1p(comp["freq_90d"])
        + a["a3_reciprocity"] * comp["reciprocity"]
        + a["a4_seniority_touch"] * comp["seniority_touch"]
        + a["a5_channel_diversity"] * comp["channel_diversity"]
        + a["bias"]
    )
    return _sigmoid(z), comp


def compute_all(session: Session, company_domain: str | None = None) -> list[WarmthRow]:
    """Score every person (optionally one company) and persist to warmth."""
    now = datetime.now()
    query = session.query(PersonRow)
    if company_domain:
        query = query.filter(PersonRow.company_id == f"company:{company_domain.lower()}")
    rows: list[WarmthRow] = []
    for person in query.all():
        interactions = (
            session.query(InteractionRow).filter(InteractionRow.person_id == person.id).all()
        )
        score, comp = score_person(person, interactions, now)
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
