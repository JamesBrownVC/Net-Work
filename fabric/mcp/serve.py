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


def main() -> None:
    if len(sys.argv) != 2:
        print(f"usage: python -m fabric.mcp.serve <{ '|'.join(registry.CONNECTOR_CLASSES) }>")
        raise SystemExit(2)
    build_server(registry.get(sys.argv[1])).run()


if __name__ == "__main__":
    main()
