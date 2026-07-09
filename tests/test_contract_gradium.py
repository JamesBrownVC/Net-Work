from __future__ import annotations

from tests.conftest import contract_check


def test_contract() -> None:
    contract_check("gradium")


def test_two_transcripts_raw_text_no_objections() -> None:
    from fabric import registry
    from fabric.schema import Transcript

    connector = registry.get("gradium")
    transcripts = [
        e
        for raw in connector.pull(since=None)
        for e in connector.normalize(raw)
        if isinstance(e, Transcript)
    ]
    assert len(transcripts) == 2
    assert all(t.objections_json == [] for t in transcripts)
    assert any("reconciliation" in t.text for t in transcripts)


def test_transcribe_mock() -> None:
    from fabric import registry

    out = registry.get("gradium").transcribe("call.wav")
    assert out["text"]
