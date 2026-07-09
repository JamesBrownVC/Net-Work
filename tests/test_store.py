from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from fabric import store


def _ingest_into(tmp_db: Path) -> dict[str, int]:
    from fabric import registry

    engine = store.get_engine(tmp_db)
    with Session(engine) as session:
        for connector in registry.all_connectors():
            for raw in connector.pull(since=None):
                store.upsert(session, connector.normalize(raw))
        session.commit()
        return store.table_counts(session)


def test_ingest_idempotent_and_acceptance_counts(tmp_path: Path) -> None:
    db = tmp_path / "acr_test.db"
    first = _ingest_into(db)
    second = _ingest_into(db)
    assert first == second, "re-running ingest must never duplicate rows"
    assert first["companies"] >= 25
    assert first["people"] >= 60
    assert first["interactions"] >= 1500
    assert first["signals"] >= 6
    assert first["transcripts"] == 2
    assert first["references"] == 6


def test_mcp_server_lists_tools() -> None:
    import asyncio

    from fabric import registry
    from fabric.mcp.serve import build_server

    server = build_server(registry.get("fullenrich"))
    tools = asyncio.run(server.list_tools())
    assert {"health", "pull", "enrich_company", "lookalikes"} <= {t.name for t in tools}


def test_mcp_enrich_company_returns_fixture_data() -> None:
    import asyncio

    from fastmcp import Client

    from fabric import registry
    from fabric.mcp.serve import build_server

    async def call() -> dict:
        async with Client(build_server(registry.get("fullenrich"))) as client:
            result = await client.call_tool("enrich_company", {"domain": "novapay.io"})
            return result.data

    block = asyncio.run(call())
    assert block["company"]["domain"] == "novapay.io"
    assert len(block["people"]) == 35
