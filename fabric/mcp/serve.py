"""Thin FastMCP wrapper: every connector becomes an MCP server with identical
code paths to direct Python calls.

Usage: python -m fabric.mcp.serve <connector>
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from fabric import registry
from fabric.connectors.base import FixtureConnector


def build_server(connector: FixtureConnector) -> FastMCP:
    mcp: FastMCP = FastMCP(f"acr-{connector.name}")

    @mcp.tool(name="health", description=f"Health status of {connector.name}")
    def health() -> str:
        return connector.health().value

    @mcp.tool(name="pull", description="Pull raw records, optionally since an ISO datetime")
    def pull(since: str | None = None) -> list[dict[str, Any]]:
        dt = datetime.fromisoformat(since) if since else None
        return [r.model_dump() for r in connector.pull(dt)]

    for method_name in registry.EXTRA_TOOLS.get(connector.name, ()):
        method = getattr(connector, method_name)
        mcp.tool(method, name=method_name, description=method.__doc__ or method_name)

    return mcp


def build_engines_server() -> FastMCP:
    """Layer 2 engines exposed over MCP: allocator, fortress, warmth."""
    from sqlalchemy.orm import Session

    from engines import allocator, fortress
    from engines import warmth as warmth_engine
    from fabric.store import get_engine

    mcp: FastMCP = FastMCP("acr-engines")

    @mcp.tool(name="allocator_solve", description="MCKP allocation plan under budgets")
    def allocator_solve(hours: float = 8.0, eur: float = 900.0, greedy: bool = False) -> dict:
        return allocator.solve(hours, eur, greedy=greedy)

    @mcp.tool(name="fortress_solve", description="Top-3 intro paths to a target title")
    def fortress_solve(company: str, target: str, v_deal: float = 50_000.0) -> dict:
        return fortress.solve(company, target, v_deal)

    @mcp.tool(name="fortress_fail_edge", description="Fail an intro edge and re-solve")
    def fortress_fail_edge(
        company: str, target: str, from_person: str, to_person: str,
        v_deal: float = 50_000.0,
    ) -> dict:
        return fortress.fail_edge(company, target, from_person, to_person, v_deal)

    @mcp.tool(name="warmth_get", description="Warmth score + components for a person id")
    def warmth_get(person_id: str) -> dict | None:
        with Session(get_engine()) as session:
            return warmth_engine.get(session, person_id)

    return mcp


def main() -> None:
    if len(sys.argv) != 2:
        names = "|".join([*registry.CONNECTOR_CLASSES, "engines"])
        print(f"usage: python -m fabric.mcp.serve <{names}>")
        raise SystemExit(2)
    name = sys.argv[1]
    server = build_engines_server() if name == "engines" else build_server(registry.get(name))
    server.run()


if __name__ == "__main__":
    main()
