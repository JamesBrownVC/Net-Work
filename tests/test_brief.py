from __future__ import annotations


def test_sillage_provider_cached_fallback() -> None:
    """With no live key, the provider returns cached insurer signals."""
    from fabric import sillage_provider

    assert sillage_provider.is_insurer("axa.fr")
    result = sillage_provider.signals_for("axa.fr")
    assert result["source"] == "cached"
    assert result["signals"]
    assert {"buying_intent"} <= {s["kind"] for s in result["signals"]}
    # unknown domain -> empty, source none
    assert sillage_provider.signals_for("not-an-insurer.example")["source"] == "none"


def test_all_13_insurers_have_cached_signals() -> None:
    from fabric import sillage_provider

    accounts = sillage_provider.insurer_accounts()
    assert len(accounts) == 13
    for a in accounts:
        assert sillage_provider.signals_for(a["domain"])["signals"], a["domain"]


def test_brief_healthy_vs_at_risk_differ_and_cite_evidence() -> None:
    """The two-account proof: a healthy warm account and an at-risk account
    produce visibly different, evidence-backed briefs."""
    from agents.brief import build_brief

    healthy = build_brief("novapay.io")
    at_risk = build_brief("cargoluxdigita.example")

    assert healthy["account"]["health"] == "Healthy"
    assert at_risk["account"]["health"] == "At risk"

    # sentiment clearly diverges
    assert healthy["relationship_health"]["recent_sentiment"] > 0.2
    assert at_risk["relationship_health"]["recent_sentiment"] < -0.2

    # at-risk account surfaces risk flags, each cited to a source interaction id
    risks = at_risk["relationship_health"]["risk_flags"]
    assert risks
    for r in risks:
        assert r["evidence"].startswith(("interaction:", "transcript:"))

    # healthy account surfaces champion signals, cited
    champs = healthy["relationship_health"]["champion_signals"]
    assert champs
    for c in champs:
        assert c["evidence"]


def test_brief_insurer_uses_sillage_and_is_honest_about_missing_content() -> None:
    from agents.brief import build_brief

    brief = build_brief("axa.fr")
    assert brief["account"]["signal_source"] == "cached"  # Sillage cached fallback
    assert brief["signals"]
    # no email/slack history for insurers -> honest, not invented
    assert brief["relationship_health"]["analyzed"] == 0


def test_brief_has_labeled_empty_castle_slot() -> None:
    from agents.brief import build_brief

    slot = build_brief("novapay.io")["fortress_slot"]
    assert slot["populated"] is False
    assert "fortress" in slot["data_contract"]
    assert slot["label"]


def test_calendar_returns_clickable_call_slots() -> None:
    from agents.brief import calendar

    slots = calendar()
    assert slots, "expected upcoming call slots"
    for s in slots:
        assert s["person"]["email"]
        assert s["when"]["day"] and s["when"]["time"]
        assert s["purpose"]
    # today's agenda includes the two 'today' calls even if the hour has passed
    assert any(s["when"]["day"] == "Today" for s in slots)


def test_person_brief_has_onward_intros_ranked_and_reasoned() -> None:
    from agents.brief import build_person_brief

    pb = build_person_brief("elsa.jansen@novapay.io")
    assert pb["person"]["name"] == "Elsa Jansen"
    intros = pb["onward_intros"]
    assert intros, "VP Sales should be able to introduce us onward"
    # the CRO (her manager) should be the top recommendation
    assert intros[0]["title"] == "CRO"
    assert intros[0]["rel_type"] == "manages"
    for o in intros:
        assert o["reason"] and 0.0 <= o["reachability"] <= 1.0
    # castle slot still present and empty
    assert pb["fortress_slot"]["populated"] is False


def test_person_brief_carries_call_purpose_and_health() -> None:
    from agents.brief import build_person_brief

    pb = build_person_brief("nora.eriksen@cargoluxdigita.example")
    assert pb["health"] == "At risk"  # cooled account contact
    assert "escalation" in pb["purpose"].lower()


def test_book_of_business_sentiment_anchored() -> None:
    from agents.brief import book_of_business

    rows = book_of_business()
    assert len(rows) >= 25
    # at-risk accounts must not have clearly-positive sentiment
    for r in rows:
        if r["health"] == "At risk":
            assert r["recent_sentiment"] <= 0.1, r
    # the planted cooled account is at risk
    cargolux = next(r for r in rows if r["domain"] == "cargoluxdigita.example")
    assert cargolux["health"] == "At risk"
