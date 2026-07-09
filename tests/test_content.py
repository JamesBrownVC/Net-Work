from __future__ import annotations

from sqlalchemy.orm import Session


def test_mock_analyzer_classifies_sentiment_and_flags() -> None:
    from engines.content import analyze_text_mock

    warm = analyze_text_mock(
        "Thanks so much, the team is thrilled. Best vendor we work with, happy to renew."
    )
    assert warm.sentiment == "positive"

    cooled = analyze_text_mock(
        "Leadership asked us to evaluate alternatives before the renewal; we are "
        "actively looking at a competitor and the pricing gap is hard to justify."
    )
    assert cooled.sentiment in ("negative", "tense")
    assert cooled.risk_flags  # competitor / alternatives / renewal-at-risk

    champ = analyze_text_mock(
        "Camille Nguyen publicly vouched for us in front of their CFO and keeps "
        "pushing the renewal internally."
    )
    assert champ.champion_signals


def test_account_content_summary_cites_interaction_ids() -> None:
    from engines.content import account_content_summary, analyze_account
    from fabric.store import get_engine

    with Session(get_engine()) as session:
        import asyncio

        asyncio.run(analyze_account(session, "cargoluxdigita.example", limit=12))
        summary = account_content_summary(session, "cargoluxdigita.example")
    assert summary["analyzed"] > 0
    # cooled account: negative recent sentiment and a downward trend
    assert summary["recent_sentiment"] < 0
    assert summary["sentiment_trend"] < 0
    assert summary["risk_flags"], "cooled account must surface risk flags"
    for rf in summary["risk_flags"]:
        assert rf["interaction_id"], "every risk flag cites a source interaction id"


def test_warmth_changes_measurably_with_content() -> None:
    """The proof: on an account whose cadence looks fine but whose content has
    soured, warmth WITH content analysis is measurably lower than WITHOUT."""
    from engines import warmth as warmth_engine
    from fabric.store import PersonRow, WarmthRow, get_engine

    dom = "cargoluxdigita.example"

    def account_mean(session: Session) -> float:
        rows = [
            r.score
            for _, r in session.query(PersonRow, WarmthRow)
            .join(WarmthRow, WarmthRow.person_id == PersonRow.id)
            .filter(PersonRow.company_id == f"company:{dom}")
            .all()
        ]
        return sum(rows) / len(rows)

    with Session(get_engine()) as session:
        warmth_engine.compute_all(session, dom, use_content=False)
        baseline = account_mean(session)
        warmth_engine.compute_all(session, dom, use_content=True)
        with_content = account_mean(session)

    assert with_content < baseline - 0.03, (baseline, with_content)


def test_champion_going_quiet_does_not_boost_warmth() -> None:
    """A champion 'going quiet' is a risk (tense sentiment), not a vouch, and
    must not be counted as a positive champion warmth component."""
    from engines.warmth import _content_maps
    from fabric.store import InteractionContextRow, get_engine

    with Session(get_engine()) as session:
        _person_sent, champ = _content_maps(session, "cargoluxdigita.example")
        tense_champ = (
            session.query(InteractionContextRow)
            .filter(
                InteractionContextRow.company_id == "company:cargoluxdigita.example",
                InteractionContextRow.sentiment == "tense",
                InteractionContextRow.champion_signals_json != "[]",
            )
            .count()
        )
    # There is a tense 'gone quiet' champion mention in the fixtures...
    assert tense_champ >= 1
    # ...but champion strength stays bounded (only positive/neutral vouches count)
    assert champ.get("company:cargoluxdigita.example", 0.0) <= 0.5
