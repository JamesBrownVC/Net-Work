"""Typer CLI: fabric status | pull | ingest | mcp list-tools."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta

import typer
from sqlalchemy.orm import Session

from fabric import registry, store

app = typer.Typer(help="ACR Connection Fabric CLI", no_args_is_help=True)
mcp_app = typer.Typer(help="MCP inspection", no_args_is_help=True)
app.add_typer(mcp_app, name="mcp")


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)d", value.strip())
    if match:
        return datetime.now() - timedelta(days=int(match.group(1)))
    return datetime.fromisoformat(value)


@app.command()
def status() -> None:
    """Table: connector | mode | health | last_pull | rows."""
    engine = store.get_engine()
    with Session(engine) as session:
        rows = registry.status_rows(session)
        counts = store.table_counts(session)
    header = f"{'connector':12s} {'mode':6s} {'health':7s} {'last_pull':20s} {'rows':>6s}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for r in rows:
        typer.echo(
            f"{r['connector']:12s} {r['mode']:6s} {r['health']:7s} "
            f"{r['last_pull']:20s} {r['rows']:>6s}"
        )
    typer.echo("\nstore: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


@app.command()
def pull(
    name: str,
    since: str | None = typer.Option(None, "--since", help="ISO datetime or Nd, e.g. 90d"),
) -> None:
    """Pull raw records from one connector and print a summary."""
    connector = registry.get(name)
    records = connector.pull(_parse_since(since))
    typer.echo(f"{name}: {len(records)} raw records")
    for rec in records[:5]:
        ts = rec.payload.get("ts") or rec.payload.get("call_ts") or "-"
        title = (
            rec.payload.get("subject")
            or rec.payload.get("title")
            or rec.payload.get("text", "")[:40]
            or rec.payload.get("name", "")
        )
        typer.echo(f"  [{rec.kind}] {ts} {title}")
    if len(records) > 5:
        typer.echo(f"  ... and {len(records) - 5} more")


@app.command()
def ingest(
    all_: bool = typer.Option(False, "--all", help="Ingest every connector"),
    name: str | None = typer.Argument(None),
) -> None:
    """Pull -> normalize -> upsert."""
    from scripts.ingest import ingest as run_ingest

    names = None if all_ or not name else [name]
    for cname, n in run_ingest(names).items():
        typer.echo(f"{cname:12s} upserted {n} entities")


@mcp_app.command("list-tools")
def list_tools(name: str) -> None:
    """List MCP tools exposed by a connector's server."""
    from fabric.mcp.serve import build_server

    server = build_server(registry.get(name))
    tools = asyncio.run(server.list_tools())
    for tool in sorted(tools, key=lambda t: t.name):
        typer.echo(tool.name)


if __name__ == "__main__":
    app()
